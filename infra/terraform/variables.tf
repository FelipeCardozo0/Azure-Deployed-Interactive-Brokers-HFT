# Terraform variables

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "hft-trading-rg"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "East US"
}

variable "prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "hft"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default = {
    Environment = "Production"
    Project     = "HFT Trading"
    Owner       = "Trading Team"
  }
}

# AKS Configuration
variable "aks_cluster_name" {
  description = "Name of the AKS cluster"
  type        = string
  default     = "hft-aks"
}

variable "aks_node_count" {
  description = "Number of nodes in the AKS cluster"
  type        = number
  default     = 3
}

variable "aks_vm_size" {
  description = "VM size for AKS nodes"
  type        = string
  default     = "Standard_D4s_v3"
}

variable "aks_disk_size_gb" {
  description = "Disk size for AKS nodes"
  type        = number
  default     = 100
}

# Database Configuration
variable "postgres_server_name" {
  description = "Name of the PostgreSQL server"
  type        = string
  default     = "hft-postgres"
}

variable "postgres_admin_username" {
  description = "PostgreSQL admin username"
  type        = string
  default     = "postgres"
}

variable "postgres_admin_password" {
  description = "PostgreSQL admin password"
  type        = string
  sensitive   = true
}

variable "postgres_sku_name" {
  description = "PostgreSQL SKU name"
  type        = string
  default     = "GP_Standard_D2s_v3"
}

variable "postgres_storage_mb" {
  description = "PostgreSQL storage size in MB"
  type        = number
  default     = 32768
}

# Redis Configuration
variable "redis_name" {
  description = "Name of the Redis cache"
  type        = string
  default     = "hft-redis"
}

variable "redis_capacity" {
  description = "Redis cache capacity"
  type        = number
  default     = 1
}

variable "redis_family" {
  description = "Redis cache family"
  type        = string
  default     = "C"
}

variable "redis_sku_name" {
  description = "Redis cache SKU name"
  type        = string
  default     = "Standard"
}

# Key Vault Configuration
variable "key_vault_name" {
  description = "Name of the Key Vault"
  type        = string
  default     = "hft-keyvault"
}

variable "key_vault_sku_name" {
  description = "Key Vault SKU name"
  type        = string
  default     = "standard"
}

# Event Hubs Configuration
variable "event_hubs_namespace_name" {
  description = "Name of the Event Hubs namespace"
  type        = string
  default     = "hft-eventhubs"
}

variable "event_hubs_sku" {
  description = "Event Hubs SKU"
  type        = string
  default     = "Standard"
}

variable "event_hubs_capacity" {
  description = "Event Hubs capacity"
  type        = number
  default     = 1
}

# Container Registry Configuration
variable "acr_name" {
  description = "Name of the Azure Container Registry"
  type        = string
  default     = "hftacr"
}

variable "acr_sku" {
  description = "ACR SKU"
  type        = string
  default     = "Basic"
}

# Log Analytics Configuration
variable "log_analytics_workspace_name" {
  description = "Name of the Log Analytics workspace"
  type        = string
  default     = "hft-logs"
}

variable "log_analytics_sku" {
  description = "Log Analytics SKU"
  type        = string
  default     = "PerGB2018"
}

variable "log_analytics_retention_days" {
  description = "Log Analytics retention days"
  type        = number
  default     = 30
}

# Application Insights Configuration
variable "app_insights_name" {
  description = "Name of the Application Insights instance"
  type        = string
  default     = "hft-appinsights"
}

variable "app_insights_type" {
  description = "Application Insights type"
  type        = string
  default     = "web"
}

# Networking Configuration
variable "allowed_ip_ranges" {
  description = "List of allowed IP ranges for database access"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "enable_accelerated_networking" {
  description = "Enable accelerated networking for AKS nodes"
  type        = bool
  default     = true
}

# Monitoring Configuration
variable "enable_monitoring" {
  description = "Enable monitoring and alerting"
  type        = bool
  default     = true
}

variable "enable_grafana" {
  description = "Enable Grafana dashboard"
  type        = bool
  default     = true
}

variable "enable_prometheus" {
  description = "Enable Prometheus monitoring"
  type        = bool
  default     = true
}
