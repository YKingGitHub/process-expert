'use strict';

const PRIORITY = new Map([['case_014', 0], ['case_015', 1], ['case_017', 2]]);
const ROLE_LABELS = {
  front: '正视',
  top: '俯视',
  right_side: '右视',
  left_side: '左视',
  back: '后视',
  bottom: '仰视',
  auxiliary: '辅助 / 剖视'
};
const KIND_LABELS = {
  external: '外观正投影',
  section: '剖视',
  detail: '局部详图',
  specification: '规格 / 参数图'
};
const CONFIDENCE_LABELS = {
  supported: '特征支持',
  symmetry_ambiguous: '对称歧义',
  unresolved: '未解决'
};

const state = { dataset: null, selected: null };
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[char]);
const finite = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
const number = (value, digits = 3) => finite(value)
  ? Number(value).toLocaleString('en-US', { maximumFractionDigits: digits })
  : '—';
const percent = value => finite(value) ? `${(Number(value) * 100).toFixed(3)}%` : '未测';
const vector = value => Array.isArray(value) ? `[${value.map(x => number(x, 6)).join(', ')}]` : '—';
const cross = (a, b) => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0]
];

function caseAsset(sample, path) {
  if (!path) return '';
  if (/^(?:https?:|data:|\/|\.\.\/|\.\/)/.test(path)) return path;
  if (path.startsWith('cases/')) return path;
  return `cases/${encodeURIComponent(sample.case_id)}/${path}`;
}

function registeredViews(sample) {
  return (sample.views || []).filter(view => pixelPassed(view));
}

function pixelPassed(view) {
  return Boolean(view.registered_source) && view.pixel_registration?.landmark_gate_pass === true && view.pair_status === 'landmark_calibrated_review_pending';
}

function hasAmbiguity(sample) {
  return Boolean(sample.annotation?.ambiguities?.length) ||
    (sample.views || []).some(view => view.confidence === 'symmetry_ambiguous');
}

function geometryPassed(sample) {
  return sample.legacy_geometry_validation?.geometry_gate_pass === true;
}

function sortSamples(samples) {
  return [...samples].sort((a, b) => {
    const ap = PRIORITY.has(a.case_id) ? PRIORITY.get(a.case_id) : 99;
    const bp = PRIORITY.has(b.case_id) ? PRIORITY.get(b.case_id) : 99;
    return ap - bp || a.case_id.localeCompare(b.case_id);
  });
}

function renderSummary() {
  const summary = state.dataset?.summary || {};
  const items = [
    [summary.case_count ?? state.dataset?.samples?.length ?? 0, '全部样例'],
    [summary.pose_calibrated_count ?? 0, '姿态候选'],
    [summary.unresolved_count ?? 0, '方向未解决'],
    [summary.build_failed_count ?? 0, '构建未完成'],
    [summary.registered_case_count ?? 0, '像素配准件数'],
    [summary.registered_view_count ?? 0, '人工锚点视图'],
    [summary.training_ready_count ?? 0, 'training ready']
  ];
  $('#summary').innerHTML = items.map(([value, label]) => `
    <div class="summary-item"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>
  `).join('');
}

function filterSamples() {
  const query = $('#search').value.trim().toLowerCase();
  const filter = $('#filter').value;
  return sortSamples(state.dataset.samples).filter(sample => {
    const text = `${sample.case_id} ${sample.name || ''}`.toLowerCase();
    if (query && !text.includes(query)) return false;
    if (filter === 'pilot') return registeredViews(sample).length > 0;
    if (filter === 'pose') return sample.status === 'pose_calibrated_candidate' && registeredViews(sample).length === 0;
    if (filter === 'ambiguous') return hasAmbiguity(sample);
    if (filter === 'unresolved') return sample.status !== 'pose_calibrated_candidate';
    if (filter === 'geometry_issue') return !geometryPassed(sample);
    return true;
  });
}

function listStatus(sample) {
  if (sample.status === 'build_failed') return '构建未完成';
  if (sample.status === 'unresolved') return '方向未解决';
  const registered = registeredViews(sample).length;
  if (registered) return `${registered} 个人工锚点视图`;
  return '仅姿态候选';
}

function renderList() {
  const samples = filterSamples();
  $('#visible-count').textContent = `${samples.length} / ${state.dataset.samples.length}`;
  $('#case-list').innerHTML = samples.map(sample => `
    <button class="case-link ${sample.case_id === state.selected ? 'active' : ''}" type="button" data-case="${esc(sample.case_id)}">
      <b>${PRIORITY.has(sample.case_id) ? '★ ' : ''}${esc(sample.case_id)}</b>
      <span>${esc(sample.name || '未命名零件')}</span>
      <small>${esc(listStatus(sample))} · ${geometryPassed(sample) ? 'v1 几何通过' : 'v1 几何未通过'}</small>
    </button>
  `).join('') || '<p class="browser-note">没有符合筛选条件的样例。</p>';
  document.querySelectorAll('[data-case]').forEach(button => {
    button.addEventListener('click', () => selectCase(button.dataset.case));
  });
}

function statusBadges(sample) {
  const registered = registeredViews(sample).length;
  const geometry = sample.legacy_geometry_validation || {};
  return `
    <span class="badge ${sample.status !== 'pose_calibrated_candidate' ? 'bad' : 'info'}">${sample.status === 'build_failed' ? '构建未完成' : sample.status === 'unresolved' ? '方向未解决' : '姿态已生成候选'}</span>
    <span class="badge ${registered ? 'good' : 'warn'}">${registered ? `${registered} 个视图人工锚点配准` : '像素尚未配准'}</span>
    <span class="badge ${geometry.geometry_gate_pass ? 'good' : 'bad'}">${geometry.geometry_gate_pass ? 'v1 几何检查通过' : 'v1 几何仍未通过'}</span>
    <span class="badge bad">training_ready = false</span>
  `;
}

function matrixTable(matrix) {
  if (!Array.isArray(matrix)) return '<div class="callout warn">没有生成刚体变换；本件暂不进入姿态候选。</div>';
  const headers = ['raw X', 'raw Y', 'raw Z', '平移 mm'];
  return `
    <div class="matrix-wrap">
      <table class="matrix" aria-label="原始坐标到统一坐标的四乘四矩阵">
        <thead><tr><th></th>${headers.map(x => `<th>${x}</th>`).join('')}</tr></thead>
        <tbody>${matrix.map((row, index) => `
          <tr><th>${index < 3 ? `${['X','Y','Z'][index]} canonical` : '齐次'}</th>${row.map(x => `<td>${number(x, 6)}</td>`).join('')}</tr>
        `).join('')}</tbody>
      </table>
    </div>
  `;
}

function coordinateSection(sample) {
  const basis = sample.annotation?.front_basis;
  if (!basis) {
    return `
      <section class="section-card">
        <div class="section-head"><div><h3>01 / 坐标变换</h3><p>原始 STEP → canonical</p></div></div>
        <div class="section-body"><div class="callout warn">没有足够证据选择 front basis。本件保留在数据集中，但不生成 canonical STEP 候选。</div></div>
      </section>`;
  }
  const camera = cross(basis.right, basis.up);
  return `
    <section class="section-card">
      <div class="section-head">
        <div><h3>01 / 原始 STEP → canonical 坐标</h3><p>矩阵行为 drawing-front 的右、上、朝向相机；det 必须为 +1，不允许镜像。</p></div>
        <span class="badge ${sample.rotation_determinant === 1 ? 'good' : 'bad'}">det ${number(sample.rotation_determinant, 6)}</span>
      </div>
      <div class="section-body coordinate-grid">
        <div>
          <div class="axis-list">
            <div class="axis-row"><b>+Xc</b><span>图纸正视向右 ← raw ${esc(vector(basis.right))}</span></div>
            <div class="axis-row"><b>+Yc</b><span>图纸正视向上 ← raw ${esc(vector(basis.up))}</span></div>
            <div class="axis-row"><b>+Zc</b><span>朝向正视相机 ← raw ${esc(vector(camera))}</span></div>
          </div>
          <div class="callout">只改变坐标姿态与中心位置，毫米尺度、体积、面积和原有几何误差不变。canonical 变换不会“修好”几何。</div>
        </div>
        ${matrixTable(sample.raw_to_canonical)}
      </div>
    </section>`;
}

function evidenceSection(sample) {
  const evidence = sample.annotation?.evidence || [];
  const ambiguities = [...(sample.annotation?.ambiguities || []), ...(sample.alignment_review_notes || [])];
  return `
    <section class="section-card">
      <div class="section-head"><div><h3>02 / 人工方向标定依据</h3><p>来自尺寸、孔位、台阶和 STEP 特征；不是自动识别结果。</p></div></div>
      <div class="section-body evidence-grid">
        <div><h4>支持证据</h4>${evidence.length ? `<ul>${evidence.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '<div class="callout warn">尚无可展示证据。</div>'}</div>
        <div><h4>对称与未决项</h4>${ambiguities.length ? `<ul>${ambiguities.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '<div class="callout">没有记录额外歧义。</div>'}</div>
      </div>
    </section>`;
}

function imagePanel(src, title, note, sample, extraClass = '') {
  if (!src) return `<div class="media-panel ${extraClass}"><div class="empty-media">${esc(note || '资产不存在')}</div></div>`;
  const url = caseAsset(sample, src);
  return `
    <figure class="media-panel ${extraClass}">
      <img src="${esc(url)}" alt="${esc(title)}" loading="lazy" data-zoom data-caption="${esc(title)}">
      <figcaption><strong>${esc(title)}</strong><br>${esc(note || '')}</figcaption>
    </figure>`;
}

function registrationBox(view) {
  const registration = view.pixel_registration;
  if (!registration) {
    return `<div class="callout warn">仅完成姿态提案，尚未做源图像素配准。源图与居中 SVG 不能直接叠加评价。</div>`;
  }
  const landmarks = registration.landmarks || [];
  const maxResidual = landmarks.length ? Math.max(...landmarks.map(item => Number(item.error_pixels) || 0)) : NaN;
  return `
    <div class="registration-box">
      <strong>人工 feature anchors · ${registration.landmark_gate_pass ? '阈值内，待人工复核' : '未通过阈值'}</strong>
      <table class="anchor-table">
        <thead><tr><th>锚点</th><th>输出像素残差</th></tr></thead>
        <tbody>${landmarks.map(item => `<tr><td>${esc(item.label)}</td><td>${number(item.error_pixels, 3)} px</td></tr>`).join('') || '<tr><td colspan="2">无锚点记录</td></tr>'}</tbody>
      </table>
      <p>轴向缩放差：${percent(registration.axis_scale_disagreement)} · 最大锚点残差：${number(maxResidual, 3)} px</p>
      <p>这只验证人工包围框与离散特征点；完整轮廓状态为 <code>${esc(registration.full_contour_acceptance || '未记录')}</code>，不能宣称整张图已自动验收。</p>
    </div>`;
}

function overlayPanel(view, sample) {
  if (!pixelPassed(view) || !view.reference_render) return '';
  const id = `${sample.case_id}-${view.id}`;
  const source = caseAsset(sample, view.registered_source);
  const reference = caseAsset(sample, view.reference_render);
  return `
    <figure class="media-panel overlay-panel">
      <div class="overlay-stack">
        <img src="${esc(source)}" alt="已注册真实源图" loading="lazy">
        <img id="overlay-${esc(id)}" class="reference-layer" src="${esc(reference)}" alt="参考 STEP 轮廓叠加" loading="lazy">
      </div>
      <div class="opacity-control">
        <label for="opacity-${esc(id)}">参考轮廓</label>
        <input id="opacity-${esc(id)}" type="range" min="0" max="100" value="62" data-overlay="overlay-${esc(id)}" data-output="opacity-value-${esc(id)}">
        <output id="opacity-value-${esc(id)}">62%</output>
      </div>
      <figcaption><strong>真实源图 + 参考 STEP 叠加</strong><br>仅对 registered_source 开放；拖动透明度检查轮廓和孔位。</figcaption>
    </figure>`;
}

function viewCard(view, sample) {
  const kind = KIND_LABELS[view.kind] || view.kind;
  const role = ROLE_LABELS[view.canonical_role] || view.canonical_role;
  const confidence = CONFIDENCE_LABELS[view.confidence] || view.confidence;
  const sourcePanel = imagePanel(view.source_image, '原始裁片', '保留尺寸与标注；本图本身不是已注册图。', sample);
  let media;
  let registration;
  if (view.kind === 'section') {
    media = `<div class="view-media section-only">${sourcePanel}<div class="media-panel"><div class="empty-media">剖视需要切割平面与偏移量；不会用普通外观投影冒充，也不参与外观 overlay。</div></div></div>`;
    registration = `<div class="callout warn">${esc(view.reason || '剖视未做切割平面标定。')}</div>`;
  } else if (view.kind !== 'external') {
    media = `<div class="view-media section-only">${sourcePanel}<div class="media-panel"><div class="empty-media">局部详图 / 参数图不与完整外观投影配对。</div></div></div>`;
    registration = `<div class="callout warn">${esc(view.reason || '该视图不属于完整外观正投影。')}</div>`;
  } else if (view.registered_source) {
    media = `
      <div class="view-media registered">
        ${sourcePanel}
        ${imagePanel(view.registered_source, pixelPassed(view) ? '已配准真实图像' : '配准失败诊断图', '由人工几何框与 feature anchors 变换；待完整轮廓验收。', sample)}
        ${imagePanel(view.reference_render, '参考 STEP 投影', 'canonical 坐标下的 HLR 矢量检查图。', sample)}
        ${imagePanel(view.reconstructed_render, 'CadQuery 重建投影', '与参考 STEP 使用相同相机和毫米尺度。', sample)}
        ${overlayPanel(view, sample)}
      </div>`;
    registration = registrationBox(view);
  } else {
    media = `
      <div class="view-media pose-only">
        ${sourcePanel}
        ${imagePanel(view.reference_render, '参考 STEP 投影', '仅方向已匹配；居中和像素尺度不是源图注册结果。', sample)}
        ${imagePanel(view.reconstructed_render, 'CadQuery 重建投影', '仅方向候选；不可与原图直接叠加宣称校准。', sample)}
      </div>`;
    registration = registrationBox(view);
  }
  return `
    <article class="view-card">
      <div class="view-head">
        <div><h4>${esc(view.id)} · ${esc(view.source_label || '未命名')}</h4><p>${esc(kind)} → canonical ${esc(role)}</p></div>
        <div class="badge-row">
          <span class="badge ${view.confidence === 'supported' ? 'good' : view.confidence === 'unresolved' ? 'bad' : 'warn'}">${esc(confidence)}</span>
          <span class="badge ${pixelPassed(view) ? 'good' : view.registered_source ? 'bad' : 'neutral'}">${pixelPassed(view) ? '锚点配准通过，待验收' : esc(view.pair_status || '未配对')}</span>
        </div>
      </div>
      ${media}
      <div class="view-meta">
        <div>
          <ul class="view-notes">
            <li>raw screen right ${esc(vector(view.raw_right))} · raw screen up ${esc(vector(view.raw_up))}</li>
            ${(view.notes || []).map(note => `<li>${esc(note)}</li>`).join('')}
          </ul>
        </div>
        ${registration}
      </div>
    </article>`;
}

function sourceViewsSection(sample) {
  const views = sample.views || [];
  return `
    <section class="section-card">
      <div class="section-head">
        <div><h3>03 / 原始图纸视图 ↔ STEP 投影</h3><p>只有 registered_source 才允许像素叠加；pose_only 仅说明观察方向候选。</p></div>
        <span class="badge ${registeredViews(sample).length ? 'good' : 'warn'}">${registeredViews(sample).length} / ${views.length} 已人工锚点配准</span>
      </div>
      <div class="section-body">
        <div class="view-stack">${views.length ? views.map(view => viewCard(view, sample)).join('') : '<div class="callout warn">没有已标注源视图。</div>'}</div>
      </div>
    </section>`;
}

function syntheticSection(sample) {
  const roles = ['front', 'top', 'right_side'];
  const projections = sample.canonical_projections || {};
  const mask = sample.input_view_mask || {};
  return `
    <section class="section-card">
      <div class="section-head">
        <div><h3>04 / Canonical 三视图 · GT 检查图</h3><p>由 STEP 合成的完整正投影，仅用于核对坐标与几何；不是缺失的真实图纸输入。</p></div>
      </div>
      <div class="section-body">
        <div class="callout warn">即使这里有 front / top / right-side 三张 SVG，输入掩码仍以真实原图为准；缺失视图不会由合成图补入训练输入。</div>
        <div class="synthetic-grid" style="margin-top:12px">
          ${roles.map(role => {
            const projection = projections[role];
            const label = ROLE_LABELS[role];
            if (!projection) return `<article class="synthetic-card"><header><h4>${esc(label)}</h4></header><div class="empty-media">本件尚未生成 canonical 投影</div></article>`;
            return `
              <article class="synthetic-card">
                <header><h4>${esc(label)} · ${mask[role] ? '有真实外观输入候选' : '真实输入缺失 / 未确认'}</h4></header>
                <div class="synthetic-pair">
                  <figure><img src="${esc(caseAsset(sample, projection.reference))}" alt="${esc(label)}参考 STEP" loading="lazy" data-zoom data-caption="${esc(label)} · 参考 STEP 合成检查图"><figcaption>参考 STEP · synthetic</figcaption></figure>
                  <figure><img src="${esc(caseAsset(sample, projection.reconstructed))}" alt="${esc(label)}重建 STEP" loading="lazy" data-zoom data-caption="${esc(label)} · CadQuery 重建合成检查图"><figcaption>CadQuery · synthetic</figcaption></figure>
                </div>
              </article>`;
          }).join('')}
        </div>
      </div>
    </section>`;
}

function legacySection(sample) {
  const validation = sample.legacy_geometry_validation || {};
  const metrics = validation.metrics || {};
  const failed = validation.geometry_gate_pass !== true;
  return `
    <section class="section-card">
      <div class="section-head">
        <div><h3>05 / v1 几何质量沿用</h3><p>canonical 只是刚体坐标变换，不重新评价也不提高原 CadQuery 重建质量。</p></div>
        <span class="badge ${failed ? 'bad' : 'good'}">${failed ? '原几何未通过' : '原几何检查通过 · 仍待人工验收'}</span>
      </div>
      <div class="section-body">
        <table class="metric-table">
          <tbody>
            <tr><th>v1 状态</th><td>${esc(validation.status || '未记录')}</td></tr>
            <tr><th>Boolean</th><td>${esc(validation.boolean_status || '未运行')}</td></tr>
            <tr><th>同坐标 IoU</th><td>${finite(metrics.iou_same_frame) ? number(metrics.iou_same_frame, 6) : '未测 / 无效'}</td></tr>
            <tr><th>对称差 / 参考体积</th><td>${percent(metrics.symmetric_difference_over_reference_volume)}</td></tr>
            <tr><th>姿态变换 round-trip</th><td>${number(sample.rigid_invariants?.transform_roundtrip_error_mm, 8)} mm</td></tr>
          </tbody>
        </table>
        <div class="callout ${failed ? 'bad' : ''}" style="margin-top:12px">${failed ? '本件在 v1 的几何失败仍然是失败；旋转到 canonical 坐标不能将它升级为合格标签。' : '通过的是参考 STEP 与 CadQuery 候选的几何门，不代表图纸像素、方向歧义或训练标签已经人工验收。'}</div>
      </div>
    </section>`;
}

function downloadPath(sample) {
  const download = sample.download;
  if (!download) return '';
  if (typeof download === 'string') return caseAsset(sample, download);
  const path = download.zip || download.path || download.href || download.url;
  return path ? caseAsset(sample, path) : '';
}

function downloadSection(sample) {
  const poseReady = sample.status === 'pose_calibrated_candidate';
  const zip = downloadPath(sample);
  return `
    <section class="section-card">
      <div class="section-head"><div><h3>06 / 候选资产与审计</h3><p>下载内容仍是 training_ready=false 的人工验收候选。</p></div></div>
      <div class="section-body">
        <div class="download-row">
          <a class="download-link" href="cases/${esc(sample.case_id)}/alignment.json">alignment.json</a>
          ${poseReady ? `<a class="download-link primary" href="cases/${esc(sample.case_id)}/model.py" download>canonical model.py</a><span class="badge neutral">两份 canonical STEP 均在候选 ZIP 内</span>` : ''}
          ${zip ? `<a class="download-link primary" href="${esc(zip)}" download>${poseReady ? '候选 ZIP' : '源图与审计 ZIP'}</a>` : '<span class="badge neutral">ZIP 尚未发布</span>'}
        </div>
        <p class="footer-note">坐标策略：${esc(sample.coordinate_policy || '未记录')} · 人工验收：${esc(sample.human_acceptance || 'pending')} · training_ready：${sample.training_ready === true ? 'true' : 'false'}</p>
      </div>
    </section>`;
}

function renderCase(sample) {
  const registered = registeredViews(sample).length;
  const poseOnly = sample.status === 'pose_calibrated_candidate' && !registered;
  $('#case-detail').innerHTML = `
    <header class="detail-head">
      <div><p class="eyebrow">${esc(sample.case_id)} / CANONICAL REVIEW</p><h2>${esc(sample.name || sample.case_id)}</h2><p>原始坐标可逆保留；本页只展示 v2 新增对齐候选，不改写 immutable v1。</p></div>
      <div class="badge-row">${statusBadges(sample)}</div>
    </header>
    ${sample.reason ? `<div class="callout bad">${esc(sample.reason)} ${sample.build_result?.log ? `<a href="${esc(sample.build_result.log)}">构建日志</a>` : ''}</div>` : ''}
    <div class="truth-strip">
      <div class="truth-item"><strong>姿态层</strong><span>${sample.status !== 'pose_calibrated_candidate' ? '尚未完成 canonical 候选；查看原因与日志' : 'proper rigid transform 候选；方向仍需人工确认'}</span></div>
      <div class="truth-item"><strong>像素层</strong><span>${registered ? `${registered} 个视图用人工 feature anchors 注册，完整轮廓仍待验收` : poseOnly ? '尚未注册；原图和 SVG 不可直接叠加' : '没有可注册外观视图'}</span></div>
      <div class="truth-item"><strong>训练层</strong><span>training_ready=false；合成三视图只作 GT 检查，不补真实输入</span></div>
    </div>
    ${coordinateSection(sample)}
    ${evidenceSection(sample)}
    ${sourceViewsSection(sample)}
    ${syntheticSection(sample)}
    ${legacySection(sample)}
    ${downloadSection(sample)}
  `;
  bindDetailInteractions();
}

function bindDetailInteractions() {
  document.querySelectorAll('[data-overlay]').forEach(input => {
    input.addEventListener('input', () => {
      const image = document.getElementById(input.dataset.overlay);
      const output = document.getElementById(input.dataset.output);
      if (image) image.style.opacity = Number(input.value) / 100;
      if (output) output.value = `${input.value}%`;
    });
  });
  document.querySelectorAll('[data-zoom]').forEach(image => {
    image.addEventListener('click', () => {
      const dialog = $('#lightbox');
      dialog.querySelector('img').src = image.src;
      dialog.querySelector('img').alt = image.alt;
      $('#lightbox-caption').textContent = image.dataset.caption || image.alt;
      dialog.showModal();
    });
  });
}

function selectCase(caseId, updateHash = true) {
  const sample = state.dataset.samples.find(item => item.case_id === caseId);
  if (!sample) return;
  state.selected = caseId;
  if (updateHash && location.hash !== `#${caseId}`) history.replaceState(null, '', `#${caseId}`);
  renderList();
  renderCase(sample);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function init() {
  try {
    const response = await fetch('dataset.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`dataset.json: HTTP ${response.status}`);
    const dataset = await response.json();
    if (!Array.isArray(dataset.samples)) throw new Error('dataset.json 缺少 samples 数组');
    state.dataset = dataset;
    renderSummary();
    const hash = decodeURIComponent(location.hash.slice(1));
    const defaultId = dataset.samples.some(item => item.case_id === hash)
      ? hash
      : dataset.samples.some(item => item.case_id === 'case_014') ? 'case_014' : sortSamples(dataset.samples)[0]?.case_id;
    renderList();
    if (defaultId) selectCase(defaultId, false);
  } catch (error) {
    $('#case-detail').innerHTML = `<div class="error-card"><strong>页面数据加载失败</strong><p>${esc(error.message)}</p><p>请确认本页通过 HTTP 服务打开，且 v2 <code>dataset.json</code> 已生成。</p></div>`;
    $('#summary').innerHTML = '<div class="summary-item"><strong>—</strong><span>dataset unavailable</span></div>';
  }
}

$('#search').addEventListener('input', renderList);
$('#filter').addEventListener('change', renderList);
$('#close-lightbox').addEventListener('click', () => $('#lightbox').close());
$('#lightbox').addEventListener('click', event => {
  if (event.target === $('#lightbox')) $('#lightbox').close();
});
window.addEventListener('hashchange', () => {
  if (state.dataset) selectCase(decodeURIComponent(location.hash.slice(1)), false);
});

init();
