from typing import Literal

from pydantic import BaseModel, Field

RssSourcePartitionMaintenanceStatus = Literal["completed"]


class RssSourcePartitionMaintenanceRead(BaseModel):
    status: RssSourcePartitionMaintenanceStatus = "completed"
    source_default_rows_repartitioned: int = Field(ge=0, default=0)
    source_feed_default_rows_repartitioned: int = Field(ge=0, default=0)
    source_weekly_partitions_created: int = Field(ge=0, default=0)
    source_feed_weekly_partitions_created: int = Field(ge=0, default=0)
    weeks_covered: int = Field(ge=0, default=0)
