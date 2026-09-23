from enum import Enum


class PermissionType(Enum):
    ADMIN = "enroll:autodiscovery_admin"
    HIGHER_UPLOAD_LIMIT = "enroll:higher_upload_limit"
    AI1_DATASETS = "enroll:ai1_datasets"
    ASTA_INTEGRATION = "enroll:asta_integration"
    # Read-only access to the aggregate metrics endpoints, for service clients.
    METRICS_READ = "read:autodiscovery_metrics"


# Every permission string. Used by the "none" (desktop) provider to unlock all
# gated features for the fixed local user.
ALL_PERMISSIONS: list[str] = [perm.value for perm in PermissionType]
