output "road_risk_namespace" {
  description = "Namespace prepared for Road Risk application workloads."
  value       = kubernetes_namespace_v1.road_risk.metadata[0].name
}

output "ingress_nginx_installed" {
  description = "Whether this stack installed ingress-nginx."
  value       = var.install_ingress_nginx
}

output "cert_manager_installed" {
  description = "Whether this stack installed cert-manager."
  value       = var.install_cert_manager
}

output "external_secrets_installed" {
  description = "Whether this stack installed External Secrets Operator."
  value       = var.install_external_secrets
}
