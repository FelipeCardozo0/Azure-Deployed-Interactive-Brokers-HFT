# Key Vault configuration

# Get current client configuration
data "azurerm_client_config" "current" {}

# Key Vault
resource "azurerm_key_vault" "main" {
  name                = var.key_vault_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = var.key_vault_sku_name
  soft_delete_retention_days = 7
  purge_protection_enabled = false

  # Network ACLs
  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
    virtual_network_subnet_ids = [
      azurerm_subnet.aks.id,
      azurerm_subnet.database.id,
      azurerm_subnet.redis.id
    ]
  }

  # Tags
  tags = var.tags
}

# Key Vault access policy for current user
resource "azurerm_key_vault_access_policy" "current_user" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = [
    "Get",
    "List",
    "Set",
    "Delete",
    "Recover",
    "Backup",
    "Restore"
  ]
}

# Key Vault access policy for AKS cluster
resource "azurerm_key_vault_access_policy" "aks" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = azurerm_kubernetes_cluster.main.identity[0].tenant_id
  object_id    = azurerm_kubernetes_cluster.main.identity[0].principal_id

  secret_permissions = [
    "Get",
    "List"
  ]
}
