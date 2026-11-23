# Deploys the <project> module, which pip-installs the released <project> from PyPI (project_version)
# at plan time and ships it as the Lambda. The module lives in terraform-aws-infra (create
# modules/<project> there — start from modules/ztna); this directory only selects and configures it.
# Release test loop: bump the package on PyPI -> change project_version in your var file -> apply.
module "project" {
  # source  = "cloudformer/infra/aws//modules/<project>"  # stable: a released Registry version
  # version = "0.1.0"
  source = "../../terraform-aws-infra/modules/project" # local: the working-tree module

  project_name       = var.project_name
  project_version    = var.project_version
  http_auth          = var.http_auth
  cloudflare_auth    = var.cloudflare_auth
  function_url_auth  = var.function_url_auth
  architecture       = var.architecture
  log_retention_days = var.log_retention_days
  force_destroy      = var.force_destroy
}
