# AKS cluster configuration

# Get current client configuration
data "azurerm_client_config" "current" {}

# AKS cluster
resource "azurerm_kubernetes_cluster" "main" {
  name                = var.aks_cluster_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  dns_prefix          = var.aks_cluster_name
  kubernetes_version  = "1.28"

  default_node_pool {
    name                = "system"
    node_count          = var.aks_node_count
    vm_size             = var.aks_vm_size
    os_disk_size_gb     = var.aks_disk_size_gb
    vnet_subnet_id      = azurerm_subnet.aks.id
    enable_auto_scaling = true
    min_count           = 1
    max_count           = 10
    max_pods            = 50

    # Enable accelerated networking
    dynamic "upgrade_settings" {
      for_each = var.enable_accelerated_networking ? [1] : []
      content {
        max_surge = "10%"
      }
    }
  }

  # Identity
  identity {
    type = "SystemAssigned"
  }

  # Network profile
  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
    service_cidr      = "10.1.0.0/16"
    dns_service_ip    = "10.1.0.10"
  }

  # Addon profile
  addon_profile {
    aci_connector_linux {
      enabled = false
    }

    azure_policy {
      enabled = true
    }

    http_application_routing {
      enabled = false
    }

    kube_dashboard {
      enabled = false
    }

    oms_agent {
      enabled                    = var.enable_monitoring
      log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
    }
  }

  # RBAC
  role_based_access_control {
    enabled = true
    azure_active_directory {
      managed                = true
      admin_group_object_ids = [data.azurerm_client_config.current.object_id]
    }
  }

  # Auto-scaler profile
  auto_scaler_profile {
    balance_similar_node_groups      = true
    expander                         = "priority"
    max_graceful_termination_sec     = 600
    max_node_provisioning_time       = "15m"
    max_unready_nodes                = 3
    max_unready_percentage           = 45
    new_pod_scale_up_delay           = "10s"
    new_pod_scale_up_delay_after_failure = "3m"
    scale_down_delay_after_add       = "10m"
    scale_down_delay_after_delete    = "10s"
    scale_down_delay_after_failure   = "3m"
    scan_interval                    = "10s"
    scale_down_utilization_threshold = "0.5"
    skip_nodes_with_local_storage    = true
    skip_nodes_with_system_pods      = true
  }

  # Maintenance window
  maintenance_window {
    allowed {
      day   = "Sunday"
      hours = [2, 3, 4, 5]
    }
  }

  # Tags
  tags = var.tags

  depends_on = [
    azurerm_subnet.aks,
    azurerm_log_analytics_workspace.main
  ]
}

# AKS node pool for trading workloads
resource "azurerm_kubernetes_cluster_node_pool" "trading" {
  name                  = "trading"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.main.id
  vm_size               = "Standard_D8s_v3"  # Higher performance for trading
  node_count            = 2
  os_disk_size_gb       = 200
  vnet_subnet_id        = azurerm_subnet.aks.id
  enable_auto_scaling   = true
  min_count             = 1
  max_count             = 5
  max_pods              = 50

  # Node taints for trading workloads
  node_taints = [
    "trading=true:NoSchedule"
  ]

  # Node labels
  node_labels = {
    workload = "trading"
    tier     = "compute"
  }

  # Upgrade settings
  upgrade_settings {
    max_surge = "10%"
  }

  tags = var.tags
}

# AKS node pool for monitoring
resource "azurerm_kubernetes_cluster_node_pool" "monitoring" {
  name                  = "monitoring"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.main.id
  vm_size               = "Standard_D4s_v3"
  node_count            = 1
  os_disk_size_gb       = 100
  vnet_subnet_id        = azurerm_subnet.aks.id
  enable_auto_scaling   = true
  min_count             = 1
  max_count             = 3
  max_pods              = 30

  # Node taints for monitoring workloads
  node_taints = [
    "monitoring=true:NoSchedule"
  ]

  # Node labels
  node_labels = {
    workload = "monitoring"
    tier     = "observability"
  }

  tags = var.tags
}

# AKS cluster admin role assignment
resource "azurerm_role_assignment" "aks_admin" {
  scope                = azurerm_kubernetes_cluster.main.id
  role_definition_name = "Azure Kubernetes Service Cluster Admin Role"
  principal_id         = data.azurerm_client_config.current.object_id
}

# AKS cluster contributor role assignment
resource "azurerm_role_assignment" "aks_contributor" {
  scope                = azurerm_kubernetes_cluster.main.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_kubernetes_cluster.main.identity[0].principal_id
}
