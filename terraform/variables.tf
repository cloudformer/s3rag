# ---- deploy credentials ----
variable "region" {
  type    = string
  default = "us-east-2"
}

variable "aws_profile" {
  description = "Local AWS CLI profile to use; \"\" = default credential chain"
  type        = string
  default     = ""
}

variable "assume_role_arn" {
  description = "Deploy role to assume; \"\" = none. Pick this OR aws_profile."
  type        = string
  default     = ""

  validation {
    condition     = !(var.assume_role_arn != "" && var.aws_profile != "")
    error_message = "Set either aws_profile or assume_role_arn, not both."
  }
}

# ---- app ----
variable "env" {
  description = "Environment label (tags, resource names)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  type    = string
  default = "<project>"
}

variable "project_version" {
  description = "The <project> release to deploy from PyPI. Bump this per release during testing; the module is not touched."
  type        = string
  default     = "0.1.0"
}

# ---- sign-in: two methods, each on or off; a request passes when any method that is on accepts it ----
variable "http_auth" {
  description = "HTTP Basic (the dialog on the page and the client's user/password)"
  type = object({
    enabled  = bool
    username = optional(string, "")
    password = optional(string, "")
  })
  default   = { enabled = false }
  sensitive = true
}

variable "cloudflare_auth" {
  description = "Cloudflare Access in front of the URL (team = <team>.cloudflareaccess.com, aud = the application's tag)"
  type = object({
    enabled = bool
    team    = optional(string, "")
    aud     = optional(string, "")
  })
  default = { enabled = false }
}

variable "function_url_auth" {
  description = "NONE = public URL, the sign-in above is the gate; AWS_IAM = SigV4 first (the browser console cannot sign, API only)"
  type        = string
  default     = "NONE"

  validation {
    condition     = contains(["NONE", "AWS_IAM"], var.function_url_auth)
    error_message = "function_url_auth must be NONE or AWS_IAM."
  }
}

# ---- the Lambda ----
variable "architecture" {
  description = "arm64 (Graviton, ~20% cheaper) or x86_64"
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["arm64", "x86_64"], var.architecture)
    error_message = "architecture must be arm64 or x86_64."
  }
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "force_destroy" {
  description = "Destroy the bucket with its contents on terraform destroy"
  type        = bool
  default     = true
}
