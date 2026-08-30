"""Pydantic data models for the ingestion pipeline."""

from pydantic import BaseModel, field_validator


class ProcessParam(BaseModel):
    operation_type: str          # 工序类型，如"精车"
    material_grade: str          # 材料牌号，如"45钢"
    parameter_name: str          # 参数名，如"切削速度"
    value: str                   # 数值，如"150"
    unit: str                    # 单位，如"m/min"
    conditions: str = "{}"       # JSON 字符串，查询条件
    chapter: str = ""            # 章节名
    table_ref: str               # 表格编号，如"表4-15"，不可为空
    source_page: int             # 页码，不可为 0
    extraction_method: str = "llm_extracted"
    cross_validated: int = 0     # 0=未验证, 1=已交叉验证

    @field_validator("source_page")
    @classmethod
    def page_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("source_page must be > 0")
        return v

    @field_validator("table_ref")
    @classmethod
    def table_ref_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("table_ref must not be empty")
        return v


class KnowledgeChunk(BaseModel):
    content: str
    source_page: int
    chapter: str = ""
    source: str = ""            # 书名/章节标识


class PageMarkdown(BaseModel):
    page_num: int
    markdown_text: str
    page_type: str = "unknown"  # "cutting_params" | "tolerance_fits" | "equipment_specs" | "surface_standards" | "unit_conversion" | "knowledge_table" | "plain_text"


class ToleranceFit(BaseModel):
    nominal_min: float
    nominal_max: float
    fit_code: str
    fit_type: str | None = None
    upper_deviation: float | None = None
    lower_deviation: float | None = None
    tolerance_grade: str | None = None
    standard_ref: str | None = None
    source_page: int
    chapter: str = ""
    table_ref: str = ""
    extraction_method: str = "llm_extracted"

    @field_validator("fit_code")
    @classmethod
    def fit_code_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("fit_code must not be empty")
        return v.strip()

    @field_validator("source_page")
    @classmethod
    def tf_page_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("source_page must be > 0")
        return v

    @field_validator("nominal_max")
    @classmethod
    def nominal_max_must_exceed_min(cls, v, info):
        nominal_min = info.data.get("nominal_min")
        if nominal_min is not None and v <= nominal_min:
            raise ValueError(f"nominal_max ({v}) must be > nominal_min ({nominal_min})")
        return v


class EquipmentSpec(BaseModel):
    equipment_type: str | None = None
    model_number: str | None = None
    param_name: str
    param_value: str | None = None
    param_unit: str | None = None
    source_page: int
    chapter: str = ""
    table_ref: str = ""
    extraction_method: str = "llm"


class SurfaceStandard(BaseModel):
    machining_method: str
    process_condition: str | None = None
    ra_min: float | None = None
    ra_max: float | None = None
    rz_min: float | None = None
    rz_max: float | None = None
    applicable_material: str | None = None
    standard_ref: str | None = None
    source_page: int
    chapter: str = ""
    table_ref: str = ""
    extraction_method: str = "llm_extracted"

    @field_validator("machining_method")
    @classmethod
    def machining_method_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("machining_method must not be empty")
        return v.strip()

    @field_validator("source_page")
    @classmethod
    def ss_page_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("source_page must be > 0")
        return v

    @field_validator("ra_max")
    @classmethod
    def ra_max_must_exceed_min(cls, v, info):
        ra_min = info.data.get("ra_min")
        if v is not None and ra_min is not None and v < ra_min:
            raise ValueError(f"ra_max ({v}) must be >= ra_min ({ra_min})")
        return v
