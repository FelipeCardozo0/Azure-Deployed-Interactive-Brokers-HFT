# Event Hubs configuration

# Event Hubs namespace
resource "azurerm_eventhub_namespace" "main" {
  name                = var.event_hubs_namespace_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = var.event_hubs_sku
  capacity            = var.event_hubs_capacity
  auto_inflate_enabled = true
  maximum_throughput_units = 20

  # Network rules
  network_rulesets {
    default_action = "Deny"
    virtual_network_rule {
      subnet_id = azurerm_subnet.aks.id
    }
  }

  # Tags
  tags = var.tags
}

# Event Hubs authorization rule
resource "azurerm_eventhub_namespace_authorization_rule" "main" {
  name                = "RootManageSharedAccessKey"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = azurerm_resource_group.main.name
  listen              = true
  manage              = true
  send                = true
}

# Event Hub for ticks
resource "azurerm_eventhub" "ticks" {
  name                = "ticks"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 4
  message_retention   = 1
}

# Event Hub for bars
resource "azurerm_eventhub" "bars" {
  name                = "bars"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 4
  message_retention   = 1
}

# Event Hub for signals
resource "azurerm_eventhub" "signals" {
  name                = "signals"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 2
  message_retention   = 1
}

# Event Hub for orders
resource "azurerm_eventhub" "orders" {
  name                = "orders"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 2
  message_retention   = 1
}

# Event Hub for fills
resource "azurerm_eventhub" "fills" {
  name                = "fills"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 2
  message_retention   = 1
}

# Event Hub for risk events
resource "azurerm_eventhub" "risk_events" {
  name                = "risk-events"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 2
  message_retention   = 1
}

# Event Hub for metrics
resource "azurerm_eventhub" "metrics" {
  name                = "metrics"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 2
  message_retention   = 1
}

# Event Hubs connection string secret
resource "azurerm_key_vault_secret" "eventhubs_connection_string" {
  name         = "eventhubs-connection-string"
  value        = azurerm_eventhub_namespace_authorization_rule.main.primary_connection_string
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_key_vault_access_policy.current_user]
}
