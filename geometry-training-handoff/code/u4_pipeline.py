#!/usr/bin/env python3
"""U4+U5:图纸 → 抽参 → 物理校验 → 建模 → 自检重试 管线

针对第一轮盲测(4/4 失败)暴露的问题设计:
  1. 体积会骗人(两个大错互相抵消)  → 验收同时卡 体积/表面积/bbox 三项
  2. 模型把内孔直径当外径(孔比外径大)→ validate() 物理校验拦截
  3. "槽宽=0"绕过防实心                → 声明为 0 的特征必须给佐证,且交叉比对转录里未被使用的尺寸
  4. "各段之和须等于总长"诱导篡改分段  → 只报告不自洽,不强制凑数
  5. 纯 schema 不够(曾返回别的零件)  → 两段式:先逐条转录,再基于转录填参数

**盲测协议由代码保证**:给模型的字段结构由模板 spec 反射得到,所有数值抹成 <number>,
不可能泄露真值或模板参数。

用法(必须用 loop 的 venv):
  cd "/Users/macsean/Desktop/AI 工艺/实验-工艺规程Loop" && \
    ./.venv/bin/python ../training_loop/tools/geometry_truth/u4_pipeline.py end_cover 3
"""
from __future__ import annotations
import os, sys, json, re, time, importlib.util, datetime
import warnings; warnings.filterwarnings("ignore")

PROJ = '/Users/macsean/Desktop/AI 工艺'
LOOP = os.path.join(PROJ, '实验-工艺规程Loop')
GT = os.path.join(PROJ, 'training_loop', 'tools', 'geometry_truth')
BUILDERS = os.path.join(GT, 'builders')
TRUTH_DIR = os.path.join(PROJ, '图纸及数模20250310', '3D数模')
CASES = os.path.join(PROJ, 'training_loop', 'cases')
OUT = os.path.join(GT, 'u4_runs')

sys.path.insert(0, LOOP)
from build123d import import_step, export_step          # noqa: E402
from src.providers import call_model                     # noqa: E402

# 形状族配置:模板模块 / 建模函数 / 示例 spec 变量(只取字段结构,不取数值)
FAMILIES = {
    'hollow_tube':  dict(module='hollow_tube',  fn='build_hollow_tube',  spec_var='WAITONG',      part='外筒',   case='002_外筒'),
    'tapered_rod':  dict(module='tapered_rod',  fn='build_tapered_rod',  spec_var='ZHUIGAN',      part='锥杆',   case='008_锥杆'),
    'locating_pin': dict(module='locating_pin', fn='build_stepped_pin',  spec_var='LOCATING_PIN', part='定位销', case='003_定位销'),
    'end_cover':    dict(module='end_cover',    fn='build_channel_plate', spec_var='DUANGAI',     part='端盖',   case='004_端盖'),
}

TOL = {'vol': 2.0, 'area': 5.0, 'bbox': 2.0}   # 验收阈值(%)


# ── 载入模板模块 ──────────────────────────────────────────────
def load_family(fam):
    cfg = FAMILIES[fam]
    path = os.path.join(BUILDERS, cfg['module'] + '.py')
    spec = importlib.util.spec_from_file_location('bld_' + fam, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, cfg['fn'], None)
    if fn is None:
        raise RuntimeError(f"{cfg['module']}.py 里没有函数 {cfg['fn']}")
    example = getattr(mod, cfg['spec_var'], None)
    if example is None:
        cands = [k for k in dir(mod) if k.isupper() and isinstance(getattr(mod, k), dict)]
        if not cands:
            raise RuntimeError(f"{cfg['module']}.py 里找不到示例 spec 字典")
        example = getattr(mod, cands[0])
    return cfg, fn, example


def skeleton(obj):
    """把 spec 的数值全部抹成占位符,只保留字段结构 —— 盲测协议的代码保证。"""
    if isinstance(obj, dict):
        return {k: skeleton(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [skeleton(obj[0])] if obj else []
    if isinstance(obj, bool):
        return '<bool>'
    if isinstance(obj, (int, float)):
        return '<number>'
    if isinstance(obj, str):
        return '<string>'
    return None


def assert_feedback_safe(feedback, transcript, seen_specs, seen_metrics):
    """反馈里出现的每个数,必须能追溯到**模型自己说过的话**
    (它的转录、它给过的参数、或由这些参数建出来的几何)。

    这保证重试反馈只是"把它自己的话回放给它",没有注入任何外部知识 —— 尤其没有真值。
    """
    if not feedback:
        return
    # 按**数值**比对(不是字符串),否则 "18" 与 "18.0" 会误判
    known = {round(float(n), 3) for n in NUM_RE.findall(transcript or '')}
    for src in list(seen_specs) + list(seen_metrics):
        acc = []
        collect_numbers(src, acc)
        known |= {round(x, 3) for x in acc}
    bad = []
    for n in NUM_RE.findall(feedback):
        f = float(n)
        if f <= 1.0:                      # 轴序号、阈值等小整数不追究
            continue
        if not any(abs(f - k) < 1e-3 for k in known):
            bad.append(n)
    if bad:
        raise RuntimeError(f'重试反馈疑似注入外部数值(可能泄露真值):{sorted(set(bad))}')


def assert_no_leak(prompt, example):
    """再上一道保险:提示词里不得出现示例 spec 中的任何数值。"""
    leaked = []
    def walk(o):
        if isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            s = f'{o:g}'
            if len(s) >= 3 and s in prompt:
                leaked.append(s)
    walk(example)
    if leaked:
        raise RuntimeError(f'盲测协议破坏:提示词疑似泄露数值 {sorted(set(leaked))}')


# ── 几何测量 ──────────────────────────────────────────────────
def measure(obj):
    bb = obj.bounding_box()
    return {'volume': float(obj.volume), 'area': float(obj.area),
            'bbox': sorted([round(float(bb.size.X), 3), round(float(bb.size.Y), 3), round(float(bb.size.Z), 3)])}


def truth_metrics(part):
    p = os.path.join(TRUTH_DIR, part + '.STEP')
    return measure(import_step(p))


def pct(a, b):
    return None if not b else round((a - b) / b * 100, 3)


# ── 第一段:逐条转录 ──────────────────────────────────────────
TRANSCRIBE_PROMPT = """你是工程图判读员。请**逐条转录**这张机械工程图上的**每一个**标注,不要遗漏。

必须包含:
- 主视图/剖视图上的所有尺寸(直径、长度、角度、半径、公差)
- **所有局部放大详图**(如 I 2:1、II 2:1、A-A、B-B)里的每一个尺寸 —— 这些最容易漏
- 技术要求文字

每条一行,格式:
  <标注原文> | <所在视图> | <它标的是什么(指向哪个特征)>

只做转录,**不要**推断零件结构,**不要**输出 JSON。看不清的写"看不清"。"""


def transcribe(png):
    """第一段:看图。用视觉模型 glm-4.6v —— 实测它转录很准。"""
    return call_model('digitize', TRANSCRIBE_PROMPT, files=[png], timeout=300)


class TechFail(Exception):
    """技术故障(网络/额度/权限)——**不是**模型能力问题,绝不可计入成绩。"""


def _assign_stream(prompt, timeout=900):
    """assign 角色的**流式**调用。

    为什么不用项目的 call_model:它是非流式的,而 GLM-5.2 推理耗时 3 分半,
    TokenHub 网关在 258s 就 504 掐断(实测)。流式下数据持续流动,网关不掐。
    这里只覆盖 assign 一个角色,**不改共用的 providers.py**,避免影响项目其他流程。

    密钥从 providers.yaml 指定的 Keychain 条目现取,不打印、不落盘。
    """
    import yaml, subprocess, requests
    cfg = yaml.safe_load(open(os.path.join(LOOP, 'providers.yaml'), encoding='utf-8'))
    provider_name, model = cfg['roles'][ASSIGN_ROLE].split('/', 1)
    prov = cfg['providers'][provider_name]
    key = subprocess.run(['security', 'find-generic-password', '-w', '-s', prov['key_keychain']],
                         capture_output=True, text=True).stdout.strip()
    if not key:
        raise TechFail(f"Keychain 条目 {prov['key_keychain']} 取不到密钥")

    parts, usage = [], {}
    with requests.post(prov['base_url'].rstrip('/') + '/chat/completions',
                       headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                       json={'model': model, 'messages': [{'role': 'user', 'content': prompt}],
                             'stream': True},
                       timeout=timeout, stream=True) as r:
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}: {r.text[:160]}')
        for raw in r.iter_lines():
            if not raw or not raw.startswith(b'data: '):
                continue
            chunk = raw[6:].decode('utf-8', 'ignore')
            if chunk.strip() == '[DONE]':
                break
            try:
                j = json.loads(chunk)
            except Exception:
                continue
            if j.get('usage'):
                usage = j['usage']
            for ch in j.get('choices', []):
                piece = (ch.get('delta') or {}).get('content')
                if piece:
                    parts.append(piece)
    text = ''.join(parts)
    if not text.strip():
        raise RuntimeError('流式返回为空(可能只有推理内容、没有正文)')
    try:   # 记账:走自建流式通道,不经 call_model,故自行落一行
        with open(os.path.join(GT, 'u4_runs', 'assign_costs.csv'), 'a') as f:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')},{ASSIGN_ROLE},{model},"
                    f"{usage.get('prompt_tokens','')},{usage.get('completion_tokens','')}\n")
    except Exception:
        pass
    return text


ASSIGN_ROLE = os.environ.get('U4_ASSIGN_ROLE', 'assign')


def call_assign(prompt):
    """第二段:推理。**不给图**,只给转录,交更强的文本模型(GLM-5.2)。

    分工理由(实测):glm-4.6v 转录 7/7 全对,但"这个尺寸属于哪个特征"的推理会来回摆
    (端盖五轮在"漏槽"与"孔起点错"之间震荡)。把"看"与"想"拆开,各用所长。
    刻意不传图:逼它基于转录做推理,而不是重新猜图。

    **绝不降级到弱模型**:早期版本超时时会悄悄回退 glm-4.6v,
    结果把"网络没通"混成了"GLM-5.2 做不到",污染了外筒/锥杆两次评测。
    现在:同一模型重试 3 次;仍失败则抛 TechFail,该次运行记为技术故障、不产生能力分。
    """
    last = None
    for i in range(3):
        try:
            # 必须走流式。实测同一请求:非流式 HTTP 504(网关 258s 掐断),
            # 流式 HTTP 200(首块 3s、总计 208s)。GLM-5.2 要思考 ~1 万 token、
            # 耗时 3 分半,超过 TokenHub 网关的非流式等待上限。
            return _assign_stream(prompt, timeout=900)
        except Exception as e:
            last = e
            print(f'  [assign 第 {i+1}/3 次失败:{type(e).__name__}: {str(e)[:70]}] '
                  f'重试**同一模型**(绝不降级)')
            if i < 2:
                time.sleep(8 * (i + 1))
    raise TechFail(f'{ASSIGN_ROLE} 连续 3 次失败:{type(last).__name__}: {str(last)[:140]}')


# ── 第二段:基于转录填参数 ────────────────────────────────────
def assign_prompt(transcript, skel, feedback=None, prev_spec=None):
    p = f"""下面是你刚才从这张工程图上逐条转录的全部标注:

--- 转录开始 ---
{transcript}
--- 转录结束 ---

请把它们组织成下面这个 JSON 结构(这是建模程序要的字段结构;`<number>` 表示该处需要你填一个数)。

{json.dumps(skel, ensure_ascii=False, indent=1)}

规则(重要):
1. **每个数值都必须来自上面的转录**。在 JSON 之外,另给一个 "evidence" 对象,
   为每个参数写明它依据转录中的哪一条(原文抄一遍)。
2. 若你认为某个特征**不存在**(例如把某个尺寸填 0 或留空数组),
   必须在 evidence 里写明"图纸上没有该特征"的依据 —— 不能默认填 0。
3. **区分内孔与外轮廓**:内孔/内腔的直径必然**小于**同位置的外轮廓直径。填之前自检一遍。
4. 若各段长度与总长对不上,**如实报告不一致**(在 evidence 里写),
   **不要**为了凑总长去改某一段的长度。
5. **有些参数图纸不会直接标注,而是由对称性/贯通关系决定** —— 这类必须按几何关系
   填出具体数值,**不要填 null**。例如:特征居中时其中心坐标就是 0;
   孔从某个面起算、贯穿到另一个面时,起止位置就等于那两个面的位置。
   这种情况在 evidence 里写明"由对称/贯通关系确定",不要写"图纸没有标注"。
6. **坐标约定(务必遵守)**:轴向/厚度方向的位置(字段名形如 z0/z1/x0/x1/z/x_end)
   一律**以零件的一端端面为 0**,沿轴正方向递增,取值必须落在 `0 ~ 总长(或总厚)` 之间。
   **不要使用以零件中心为原点的坐标**(不要出现负数)。
   例如一个贯穿件的通孔,应写成 `从某端面位置 → 另一端面位置`,而不是 `-半高 → +半高`。
   而横向定位(字段名形如 x / y,表示特征在截面内的位置)才是以中心为原点、居中时为 0。
5. 输出格式:先输出 ```json 代码块包住的 {{"spec": {{...}}, "evidence": {{...}}}},不要别的。"""
    if feedback:
        if prev_spec is not None:
            # 增量修补:把上一版原样给它,只让它改被指出的地方。
            # 早期"每轮从头重答"导致震荡 —— 端盖修好槽就丢了孔起点、修好孔又丢了槽,五轮不收敛。
            p += f"""

⚠️ 你上一次给出的答案是:
```json
{json.dumps(prev_spec, ensure_ascii=False, indent=1)}
```

它**没有通过校验**,问题如下(只指出哪里不对,不会告诉你正确答案):
{feedback}

请在**保留其余字段原样不变**的前提下,只修正上面被指出的地方。
**不要从头重答** —— 没被指出问题的部分是对的,改动它们只会引入新错误。
输出完整的 JSON(改过的和没改的字段都要有)。"""
        else:
            p += f"""

⚠️ 上一次你的答案没通过校验,具体问题如下
(只告诉你哪里不对,不会告诉你正确答案):
{feedback}"""
    return p


JSON_RE = re.compile(r'```(?:json)?\s*(\{.*?\})\s*```', re.S)


def parse_reply(reply):
    m = JSON_RE.search(reply)
    raw = m.group(1) if m else reply[reply.find('{'): reply.rfind('}') + 1]
    data = json.loads(raw)
    return data.get('spec', data), data.get('evidence', {})


# ── 物理校验 ──────────────────────────────────────────────────
# 只排除"前面是数字或小数点"的情况。**不能用 \w**:φ/Φ/⌀/R/SR 在 Unicode 里算字母,
# 用 \w 会把 φ63.2、R6.35 这类直径/半径标注整个滤掉(实测外筒因此只剩 4 个尺寸)。
NUM_RE = re.compile(r'(?<![\d.])(\d+(?:\.\d+)?)')


def collect_numbers(obj, acc):
    if isinstance(obj, dict):
        for v in obj.values(): collect_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj: collect_numbers(v, acc)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        acc.append(float(obj))


# "12. " 这类列表行号。**必须要求分隔符后有空白**,否则 "13.5" 会被当成序号 13. 而只剩 5
# (实测端盖因此丢了 13.5 和 3.5)。
LIST_PREFIX_RE = re.compile(r'^\s*\d+\s*[.、)]\s+')
COUNT_PREFIX_RE = re.compile(r'^\s*\d+\s*-')          # "4-φ5" / "2-R2" 里的数量前缀
ANGLE_RE = re.compile(r'\d+(?:\.\d+)?\s*°')           # 角度:模板用锥段隐式表达,不作独立参数


def transcript_dims(transcript):
    """从转录中取出**真正的尺寸数值**。

    踩过的坑(都会制造假违规、把模型逼疯):
      - 转录常是编号列表,"12. 10 | …" 里的 12 是**行号**不是尺寸(实测外筒被误判出 6~16 一串连号)
      - "4-φ5" 里的 4 是**数量**
      - "30°/45°" 是角度,模板用锥段隐式表达,永远不会出现在参数里 → 会成为永不消失的假违规
      - 公差(±0.1/+0.2)与粗糙度(3.2/1.6)不是特征尺寸
    """
    ROUGH_VALS = {0.4, 0.8, 1.6, 3.2, 6.3, 12.5, 25.0}   # 标准表面粗糙度 Ra 系列
    dims = []
    for line in (transcript or '').splitlines():
        if '|' not in line or '技术要求' in line or '粗糙度' in line or '公差' in line:
            continue
        # 粗糙度陷阱:转录常把 Ra 值写成"表面/其余"而不写"粗糙度",于是被当成尺寸。
        # 但同一个数字可能同时是真尺寸(外筒的 3.2 既是凸缘长、又是 Ra 值),
        # 所以**不能按数值一刀切** —— 只在"描述提到表面/其余"且"数值属 Ra 系列"时才跳过。
        desc = line.split('|', 1)[1] if '|' in line else ''
        if '其余' in line or ('表面' in desc and
                              any(abs(float(n) - rv) < 1e-6
                                  for n in NUM_RE.findall(line.split('|')[0])
                                  for rv in ROUGH_VALS)):
            continue
        head = line.split('|')[0]
        head = LIST_PREFIX_RE.sub('', head)     # 先去行号
        head = COUNT_PREFIX_RE.sub('', head)    # 再去数量前缀
        head = ANGLE_RE.sub('', head)           # 去掉角度
        for n in NUM_RE.findall(head):
            f = float(n)
            if f > 1.0:                          # 滤掉 ±0.1 / +0.2 这类公差
                dims.append(round(f, 3))
    return sorted(set(dims), reverse=True)


COORD_KEYS = ('z0', 'z1', 'x0', 'x1', 'x', 'y', 'z', 'x_end')   # 位置类字段:填 0 合法


def _norm_path(p):
    """把 bore[0].x 归一成 bore[].x,便于和模板示例对位比较。"""
    return re.sub(r'\[\d+\]', '[]', p)


def optional_paths(example):
    """模板示例里本来就是 None/空 的字段 = 该形状族**允许该特征不存在**。

    锥杆实测教训:它本来就没有径向孔(ZHUIGAN['radial_holes'] is None),
    模型四轮都正确答"没有",却被校验器四轮判成"缺失",白跑一件。
    """
    out = set()
    def walk(o, path=''):
        if isinstance(o, dict):
            if not o and path: out.add(_norm_path(path))
            for k, v in o.items(): walk(v, f'{path}.{k}' if path else k)
        elif isinstance(o, list):
            if not o and path: out.add(_norm_path(path))
            else:
                for x in o: walk(x, f'{path}[]')
        elif o is None and path:
            out.add(_norm_path(path))
    walk(example or {})
    return out


def validate(spec, evidence, transcript, example=None):
    """纯代码物理校验。返回违规清单(空 = 通过)。"""
    OPTIONAL = optional_paths(example)
    v = []

    # 1) 外轮廓最大尺寸(用于判定内孔是否越界)
    # 只能拿**直径**和直径比。早期版本把 length(总长)也算作"外轮廓尺寸",
    # 于是用内孔直径去比总长(52 < 95 恒成立),这条物理校验从来没生效过。
    outer_dias, cross_sections = [], []
    def scan_outer(o, inside_cav=False):
        if isinstance(o, dict):
            for k, val in o.items():
                kl = k.lower()
                cav = inside_cav or any(w in kl for w in ('bore', 'slot', 'hole', 'cav'))
                if not cav and isinstance(val, (int, float)) and not isinstance(val, bool):
                    if 'dia' in kl:                       # 外轮廓直径
                        outer_dias.append(float(val))
                    elif kl in ('width', 'thickness'):    # 板类:内孔须小于截面
                        cross_sections.append(float(val))
                scan_outer(val, cav)
        elif isinstance(o, list):
            for x in o: scan_outer(x, inside_cav)
    scan_outer(spec)
    max_outer = max(outer_dias) if outer_dias else (min(cross_sections) if cross_sections else None)

    # 2) 内孔直径必须 < 外轮廓最大直径
    if max_outer:
        bad = []
        def scan_bore(o, key=''):
            if isinstance(o, dict):
                for k, val in o.items(): scan_bore(val, k)
            elif isinstance(o, list):
                for x in o: scan_bore(x, key)
            elif isinstance(o, (int, float)) and not isinstance(o, bool):
                if 'dia' in key.lower() and float(o) > max_outer + 1e-6:
                    bad.append((key, float(o)))
        for k in ('bore', 'bores', 'slot', 'radial_holes', 'holes'):
            if k in spec: scan_bore(spec[k], k)
        for k, val in bad:
            v.append(f"物理不可能:内腔尺寸 {k}={val} 大于外轮廓最大尺寸 {max_outer}。"
                     f"你可能把内孔直径当成了外径 —— 请回图纸区分内外轮廓。")

    # 3) 缺失特征:空字典 / 空数组 / null / 0
    missing = []
    def scan_zero(o, path=''):
        if _norm_path(path) in OPTIONAL:      # 模板允许该特征不存在 → 空是合法答案
            return
        if isinstance(o, dict):
            if not o: missing.append(path + '(空对象)')
            for k, val in o.items(): scan_zero(val, f'{path}.{k}' if path else k)
        elif isinstance(o, list):
            if not o: missing.append(path + '(空数组)')
            else:
                for i, x in enumerate(o): scan_zero(x, f'{path}[{i}]')
        elif o is None:
            missing.append(path + '(null)')
        elif isinstance(o, (int, float)) and not isinstance(o, bool) and float(o) == 0.0:
            # 坐标类字段填 0 是**合法**的(端面起算就是 0)。
            # 只有"尺寸类"字段为 0 才说明特征缺失。
            # (端盖实测教训:把 z0=0 误判成缺失,与"禁止负坐标"一起把模型逼进死角,
            #  而 z0=0 在几何上与正确值等价——孔的这一段本就落在槽内、早被挖掉。)
            key = path.split('.')[-1].split('[')[0]
            if key not in COORD_KEYS:
                missing.append(path)
    scan_zero(spec)
    if missing:
        v.append(f"下列参数被判为不存在/为空/为 null:{missing[:12]}。"
                 f"模板需要这些值才能建模。若该特征确实存在,请回图纸找出它的尺寸;"
                 f"若确实不存在,请在 evidence 里给出图纸依据。")

    # 3.5) 轴向坐标不得为负 —— 模板一律以"零件一端端面 = 0",不用中心原点。
    #      (端盖实测:模型把通孔写成 -6.75~6.75,孔只钻到一半,恰好少挖 868.6 mm³)
    neg = []
    def scan_axis(o, path=''):
        if isinstance(o, dict):
            for k, val in o.items(): scan_axis(val, f'{path}.{k}' if path else k)
        elif isinstance(o, list):
            for i, x in enumerate(o): scan_axis(x, f'{path}[{i}]')
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            key = path.split('.')[-1].split('[')[0]
            if key in ('z0', 'z1', 'x0', 'x1', 'z', 'x_end') and float(o) < 0:
                neg.append((path, float(o)))
    scan_axis(spec)
    for pth, val in neg:
        v.append(f"坐标约定错误:{pth} = {val} 是负数。轴向位置一律**以零件一端端面为 0**、"
                 f"沿轴正向递增,取值应落在 0 到总长(或总厚)之间,不要用以中心为原点的坐标。"
                 f"请把它改成从端面量起的位置。")

    # 3.5) 结构完整性:模板要求的字段一个都不能少
    # (锥杆实测:模型漏写 profile 段里的 d1,直接把建模器崩成 KeyError,
    #  白白耗掉最后一次重试机会 —— 这种事应该在建模前就告诉它)
    def miss_keys(sp, ex, path=''):
        if isinstance(ex, dict) and isinstance(sp, dict):
            for k, v in ex.items():
                sub = f'{path}.{k}' if path else k
                if k not in sp:
                    if _norm_path(sub) not in OPTIONAL:
                        v_.append(sub)
                else:
                    miss_keys(sp[k], v, sub)
        elif isinstance(ex, list) and isinstance(sp, list) and ex:
            for i, item in enumerate(sp):
                miss_keys(item, ex[0], f'{path}[{i}]')
    v_ = []
    if example:
        miss_keys(spec, example)
        if v_:
            v.append(f"下列模板必填字段缺失:{v_[:12]}。每一段/每个特征都必须把字段写全,"
                     f"缺一个建模就会失败。请补齐后重新输出完整 JSON。")

    # 3.6) 每个分段/孔的轴向高度必须为正(起点 < 终点)
    def scan_seg(o, path=''):
        if isinstance(o, dict):
            for a, b in (('z0', 'z1'), ('x0', 'x1')):
                if isinstance(o.get(a), (int, float)) and isinstance(o.get(b), (int, float)):
                    if float(o[b]) <= float(o[a]):
                        v.append(f"{path or '该段'} 的 {a}={o[a]} 与 {b}={o[b]} 构成零高度或反向,"
                                 f"轴向必须 {a} < {b}。请复核该特征的起止位置。")
            for k, val in o.items(): scan_seg(val, f'{path}.{k}' if path else k)
        elif isinstance(o, list):
            for i, x in enumerate(o): scan_seg(x, f'{path}[{i}]')
    scan_seg(spec)

    # 3.7) 退化的锥:两端直径相同 —— 几何内核会直接报 "cone with two identic radii"
    def scan_cone(o, path=''):
        if isinstance(o, dict):
            t = str(o.get('type', '')).lower()
            a, b = o.get('from_dia'), o.get('to_dia')
            if 'con' in t and isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if abs(float(a) - float(b)) < 1e-9:
                    v.append(f"{path or '该段'} 标为锥(type={o.get('type')!r})但两端直径相同"
                             f"({a})—— 锥必须两端不等径。若该段本就是等径,请把 type 改为圆柱。")
            for k, val in o.items(): scan_cone(val, f'{path}.{k}' if path else k)
        elif isinstance(o, list):
            for i, x in enumerate(o): scan_cone(x, f'{path}[{i}]')
    scan_cone(spec)

    # 4) 【最有力的线索】转录里出现、却没有被任何参数用到的尺寸 —— 一定是漏读了特征
    used = []
    collect_numbers(spec, used)
    used_s = {round(u, 3) for u in used}
    unused = [d for d in transcript_dims(transcript)
              if not any(abs(d - u) < 1e-3 for u in used_s)]
    if unused:
        v.append(f"你在转录里读到了这些尺寸,却没有把它们用在任何参数上:{unused[:12]}。"
                 f"工程图上的尺寸不会白标 —— 每一个都对应一个特征。"
                 f"请回图纸看清这些尺寸各自标的是**哪个特征**(注意它们可能来自局部剖视图,"
                 f"标的是槽、台阶、凹腔这类局部特征,而不是零件的总体轮廓),然后补进参数。")

    # 4) evidence 缺失
    if not evidence:
        v.append("缺少 evidence:每个参数都必须写明依据转录中的哪一条。")

    # 5) 分段轴向范围 vs 总长(只报告,不强制)
    total = spec.get('length') or spec.get('total_len')
    if isinstance(total, (int, float)):
        ends = []
        def scan_end(o):
            if isinstance(o, dict):
                for k, val in o.items():
                    if k in ('x1', 'z1', 'x_end') and isinstance(val, (int, float)): ends.append(float(val))
                    scan_end(val)
            elif isinstance(o, list):
                for x in o: scan_end(x)
        scan_end(spec)
        if ends and max(ends) > float(total) + 1e-6:
            v.append(f"不自洽:有分段终点 {max(ends)} 超出了总长 {total}。"
                     f"请回图纸复核总长与分段位置(不要靠压缩某一段来凑)。")
    return v


# ── 建模 + 判定 ───────────────────────────────────────────────
def build_and_measure(fn, spec, part):
    solid = fn(spec)
    m = measure(solid)
    t = truth_metrics(part)
    dev = {'vol': pct(m['volume'], t['volume']), 'area': pct(m['area'], t['area']),
           'bbox': [pct(m['bbox'][i], t['bbox'][i]) for i in range(3)]}
    ok = (abs(dev['vol']) < TOL['vol'] and abs(dev['area']) < TOL['area']
          and all(abs(b) < TOL['bbox'] for b in dev['bbox']))
    return solid, m, t, dev, ok


def drawing_consistency(m, transcript):
    """自检:建出来的总体尺寸,能否在**图纸转录**里找到对应标注。

    **刻意不使用真值** —— 真实产品在推理时没有标准件可比。
    拿真值去指导重试等于拿答案教学生,做出来的成绩是假的。
    这里只做"模型自己读到的图纸尺寸 vs 它自己建出来的几何"的自洽性检查。
    (外筒那次轴向 63.3 而图纸写 95,靠这条就能自己发现。)
    """
    tnums = sorted({float(x) for x in NUM_RE.findall(transcript or '')}, reverse=True)
    viol = []
    for i, axis in enumerate(m['bbox']):
        if axis <= 0:
            continue
        if not any(abs(axis - t) / max(t, 1e-9) < 0.01 for t in tnums):
            viol.append(f"自检不通过:建出来的第 {i+1} 轴总尺寸是 {axis},"
                        f"但图纸转录里找不到与之对应的标注 —— 很可能这个方向上某个尺寸读错、"
                        f"或整段特征被漏掉了。请回图纸复核该方向的总尺寸与分段。")
    return viol


# ── 主循环 ────────────────────────────────────────────────────
def run(fam, max_retries=3):
    cfg, fn, example = load_family(fam)
    part, case = cfg['part'], cfg['case']
    png = os.path.join(CASES, case, 'input_public', 'drawing.png')
    skel = skeleton(example)
    os.makedirs(OUT, exist_ok=True)
    log = {'family': fam, 'part': part, 'attempts': [], 'accepted': False,
           'ts': datetime.datetime.now().isoformat(timespec='seconds')}

    print(f'=== {part} ({fam}) ===')
    # 转录缓存:同件重跑复用。省钱,更重要的是让实验**可控** ——
    # 固定转录后,单独考察"归位推理"这一步,不被转录的随机波动干扰
    # (实测端盖五次转录长度 339/346/349/368/399 字符,标注措辞每次都不同)。
    cache = os.path.join(OUT, f'{part}_transcript.txt')
    if os.path.exists(cache) and os.environ.get('U4_FRESH_TRANSCRIPT') != '1':
        transcript = open(cache, encoding='utf-8').read()
        print(f'第一段:复用缓存转录({len(transcript)} 字符);要重转设 U4_FRESH_TRANSCRIPT=1')
    else:
        print('第一段:逐条转录图纸标注 …')
        transcript = transcribe(png)
        open(cache, 'w', encoding='utf-8').write(transcript)
        print(f'  转录 {len(transcript)} 字符(已缓存)')
    log['transcript'] = transcript

    feedback = None
    seen_specs, seen_metrics = [], []      # 供盲测守卫追溯"模型自己说过的数"
    for attempt in range(1, max_retries + 2):
        print(f'\n--- 第 {attempt} 次抽参 ---')
        prompt = assign_prompt(transcript, skel, feedback,
                               prev_spec=(seen_specs[-1] if seen_specs else None))
        # 盲测协议(两道):
        #  ① 字段骨架里不得有任何数值(skeleton() 已抹除,这里复核)
        #  ② 重试反馈里的每个数都必须来自模型自己说过的话,不得注入外部知识/真值
        assert_no_leak(json.dumps(skel, ensure_ascii=False), example)
        assert_feedback_safe(feedback, transcript, seen_specs, seen_metrics)
        try:
            reply = call_assign(prompt)
        except TechFail as e:
            # 技术故障 ≠ 能力不足。标记后中止,accepted 记 None(未评测),不产生任何成绩。
            print(f'  ⛔ 技术故障,中止本件评测:{e}')
            log['tech_fail'] = str(e); log['accepted'] = None
            break
        rec = {'attempt': attempt, 'raw': reply}
        try:
            spec, evidence = parse_reply(reply)
        except Exception as e:
            rec['error'] = f'JSON 解析失败: {e}'
            # 反馈里不带解析器的行号列号(纯诊断数字,会触发盲测守卫且对模型无用)
            feedback = ('你的输出不是合法 JSON,无法解析。请只输出一个 ```json 代码块,'
                        '内容为 {"spec": {...}, "evidence": {...}},不要有注释、省略号或多余文字。')
            log['attempts'].append(rec); print('  ', rec['error']); continue

        seen_specs.append(spec)
        viol = validate(spec, evidence, transcript, example)
        rec['spec'] = spec; rec['violations'] = viol
        if viol:
            print('  校验未过:'); [print('   -', x) for x in viol]
            feedback = "\n".join('- ' + x for x in viol)
            log['attempts'].append(rec); continue

        try:
            solid, m, t, dev, ok = build_and_measure(fn, spec, part)
        except Exception as e:
            rec['error'] = f'建模失败: {type(e).__name__}: {e}'
            feedback = f'用你给的参数建模失败:{type(e).__name__}: {e}。请检查各段是否首尾相接、参数是否自洽。'
            log['attempts'].append(rec); print('  ', rec['error']); continue

        seen_metrics.append(m)
        # 真值偏差只用于**记分与日志**,绝不回喂给模型(否则就是拿答案教学生)
        sc = drawing_consistency(m, transcript)
        rec.update({'metrics': m, 'dev_vs_truth': dev, 'meets_truth_tol': ok, 'self_check': sc})
        print(f"  体积 {m['volume']:.1f} | [记分]真值偏差 体积{dev['vol']}% 面积{dev['area']}% bbox{dev['bbox']}")
        log['attempts'].append(rec)
        if sc:
            print('  自检未过:'); [print('   -', x) for x in sc]
            feedback = "\n".join('- ' + x for x in sc)
            continue
        # 自检通过 → 收敛。是否真的准,由真值判定记分(不影响收敛)
        log['accepted'] = ok; log['final'] = rec
        export_step(solid, os.path.join(OUT, f'{part}_u4_final.step'))
        print('  自检通过,收敛。' + ('✅ 且达到真值容差' if ok else '⚠️ 但未达真值容差(自检没抓住的错)'))
        break

    with open(os.path.join(OUT, f'{part}_u4_log.json'), 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    verdict = ('TECH_FAIL(技术故障,不作能力结论)' if log.get('tech_fail')
               else ('ACCEPTED' if log['accepted'] else 'NOT ACCEPTED'))
    print(f"\n结果:{verdict}  日志 → u4_runs/{part}_u4_log.json")
    return log


if __name__ == '__main__':
    fam = sys.argv[1] if len(sys.argv) > 1 else 'end_cover'
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    run(fam, n)
