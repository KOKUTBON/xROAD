variable "kubeconfig_path" {
  description = "Path to the kubeconfig file for the target cluster."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Optional kubeconfig context. Leave null to use the current context."
  type        = string
  default     = null
}

variable "environment" {
  description = "Deployment environment label, for example staging or production."
  type        = string
  default     = "staging"
}

variable "namespace" {
  description = "Namespace that will host the Road Risk application workloads."
  type        = string
  default     = "road-risk"
}

variable "owner_label" {
  description = "Operational owner label attached to managed Kubernetes objects."
  type        = string
  default     = "municipal-platform"
}

variable "install_ingress_nginx" {
  description = "Install ingress-nginx if the cluster does not already provide an ingress controller."
  type        = bool
  default     = true
}

variable "ingress_nginx_chart_version" {
  description = "ingress-nginx Helm chart version."
  type        = string
  default     = "4.10.1"
}

variable "install_cert_manager" {
  description = "Install cert-manager for TLS certificate automation."
  type        = bool
  default     = true
}

variable "cert_manager_chart_version" {
  description = "cert-manager Helm chart version."
  type        = string
  default     = "v1.14.5"
}

variable "install_external_secrets" {
  description = "Install External Secrets Operator for secret-manager integration."
  type        = bool
  default     = true
}

variable "external_secrets_chart_version" {
  description = "External Secrets Operator Helm chart version."
  type        = string
  default     = "0.9.20"
}
