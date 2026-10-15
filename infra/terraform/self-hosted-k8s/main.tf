provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kube_context
}

provider "helm" {
  kubernetes {
    config_path    = var.kubeconfig_path
    config_context = var.kube_context
  }
}

locals {
  common_labels = {
    "app.kubernetes.io/part-of"    = "road-risk-platform"
    "app.kubernetes.io/managed-by" = "terraform"
    "road-risk.io/environment"     = var.environment
    "road-risk.io/owner"           = var.owner_label
  }
}

resource "kubernetes_namespace_v1" "road_risk" {
  metadata {
    name = var.namespace
    labels = merge(local.common_labels, {
      "app.kubernetes.io/name" = "road-risk"
    })
  }
}

resource "helm_release" "ingress_nginx" {
  count            = var.install_ingress_nginx ? 1 : 0
  name             = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = var.ingress_nginx_chart_version
  namespace        = "ingress-nginx"
  create_namespace = true

  values = [
    yamlencode({
      controller = {
        replicaCount = 2
        metrics = {
          enabled = true
        }
        service = {
          externalTrafficPolicy = "Local"
        }
      }
    })
  ]
}

resource "helm_release" "cert_manager" {
  count            = var.install_cert_manager ? 1 : 0
  name             = "cert-manager"
  repository       = "https://charts.jetstack.io"
  chart            = "cert-manager"
  version          = var.cert_manager_chart_version
  namespace        = "cert-manager"
  create_namespace = true

  set {
    name  = "installCRDs"
    value = "true"
  }
}

resource "helm_release" "external_secrets" {
  count            = var.install_external_secrets ? 1 : 0
  name             = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  version          = var.external_secrets_chart_version
  namespace        = "external-secrets"
  create_namespace = true

  values = [
    yamlencode({
      installCRDs = true
      webhook = {
        replicaCount = 2
      }
      certController = {
        replicaCount = 2
      }
    })
  ]
}
