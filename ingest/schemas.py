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
    page_type: str = "unknown"  # "param_table" | "knowledge_table" | "plain_text"
