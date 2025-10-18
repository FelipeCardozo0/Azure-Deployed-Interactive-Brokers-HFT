# PostgreSQL Flexible Server configuration

# Random password for PostgreSQL
resource "random_password" "postgres_password" {
  length  = 32
  special = true
}

# PostgreSQL Flexible Server
resource "azurerm_postgresql_flexible_server" "main" {
  name                   = var.postgres_server_name
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "15"
  administrator_login    = var.postgres_admin_username
  administrator_password = var.postgres_admin_password != "" ? var.postgres_admin_password : random_password.postgres_password.result
  zone                   = "1"

  storage_mb = var.postgres_storage_mb
  sku_name   = var.postgres_sku_name

  backup_retention_days        = 7
  geo_redundant_backup_enabled = false

  high_availability {
    mode = "Disabled"
  }

  maintenance_window {
    day_of_week  = 0
    start_hour   = 8
    start_minute = 0
  }

  # Network configuration
  delegated_subnet_id = azurerm_subnet.database.id
  private_dns_zone_id = azurerm_private_dns_zone.postgres.id

  # SSL configuration
  ssl_enforcement_enabled = true
  ssl_minimal_tls_version_enforced = "TLS1_2"

  # Tags
  tags = var.tags

  depends_on = [
    azurerm_subnet.database,
    azurerm_private_dns_zone.postgres
  ]
}

# Private DNS zone for PostgreSQL
resource "azurerm_private_dns_zone" "postgres" {
  name                = "${var.prefix}-postgres.private.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.main.name

  tags = var.tags
}

# Private DNS zone virtual network link
resource "azurerm_private_dns_zone_virtual_network_link" "postgres" {
  name                  = "${var.prefix}-postgres-vnet-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.postgres.name
  virtual_network_id   = azurerm_virtual_network.main.id
  registration_enabled  = false

  tags = var.tags
}

# PostgreSQL database
resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = "trading"
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "utf8"
}

# PostgreSQL firewall rules
resource "azurerm_postgresql_flexible_server_firewall_rule" "aks" {
  name             = "aks-subnet"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "10.0.1.0"
  end_ip_address   = "10.0.1.255"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "database" {
  name             = "database-subnet"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "10.0.2.0"
  end_ip_address   = "10.0.2.255"
}

# PostgreSQL configuration
resource "azurerm_postgresql_flexible_server_configuration" "log_statement" {
  name      = "log_statement"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "all"
}

resource "azurerm_postgresql_flexible_server_configuration" "log_min_duration_statement" {
  name      = "log_min_duration_statement"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "1000"  # Log statements taking more than 1 second
}

resource "azurerm_postgresql_flexible_server_configuration" "shared_preload_libraries" {
  name      = "shared_preload_libraries"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "timescaledb"
}

# TimescaleDB extension
resource "azurerm_postgresql_flexible_server_configuration" "timescaledb_telemetry" {
  name      = "timescaledb.telemetry"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "off"
}

# PostgreSQL user for application
resource "azurerm_postgresql_flexible_server_active_directory_administrator" "app" {
  server_name         = azurerm_postgresql_flexible_server.main.name
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  object_id           = data.azurerm_client_config.current.object_id
  identity            = "SystemAssigned"
  login               = "app_admin"
}

# PostgreSQL connection string secret
resource "azurerm_key_vault_secret" "postgres_connection_string" {
  name         = "postgres-connection-string"
  value        = "postgresql://${azurerm_postgresql_flexible_server.main.administrator_login}:${azurerm_postgresql_flexible_server.main.administrator_password}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.main.name}?sslmode=require"
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_key_vault_access_policy.current_user]
}

# PostgreSQL admin password secret
resource "azurerm_key_vault_secret" "postgres_admin_password" {
  name         = "postgres-admin-password"
  value        = azurerm_postgresql_flexible_server.main.administrator_password
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_key_vault_access_policy.current_user]
}
