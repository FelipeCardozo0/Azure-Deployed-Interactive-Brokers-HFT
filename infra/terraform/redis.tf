# Redis Cache configuration

# Redis Cache
resource "azurerm_redis_cache" "main" {
  name                = var.redis_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  capacity            = var.redis_capacity
  family              = var.redis_family
  sku_name            = var.redis_sku_name
  enable_non_ssl_port = false
  minimum_tls_version = "1.2"

  # Network configuration
  subnet_id = azurerm_subnet.redis.id

  # Redis configuration
  redis_configuration {
    maxmemory_reserved = 2
    maxmemory_delta     = 2
    maxmemory_policy    = "allkeys-lru"
  }

  # Tags
  tags = var.tags

  depends_on = [
    azurerm_subnet.redis
  ]
}

# Redis firewall rules
resource "azurerm_redis_firewall_rule" "aks" {
  name                = "aks-subnet"
  redis_cache_name    = azurerm_redis_cache.main.name
  resource_group_name = azurerm_resource_group.main.name
  start_ip            = "10.0.1.0"
  end_ip              = "10.0.1.255"
}

resource "azurerm_redis_firewall_rule" "database" {
  name                = "database-subnet"
  redis_cache_name    = azurerm_redis_cache.main.name
  resource_group_name = azurerm_resource_group.main.name
  start_ip            = "10.0.2.0"
  end_ip              = "10.0.2.255"
}

# Redis connection string secret
resource "azurerm_key_vault_secret" "redis_connection_string" {
  name         = "redis-connection-string"
  value        = "rediss://:${azurerm_redis_cache.main.primary_access_key}@${azurerm_redis_cache.main.hostname}:${azurerm_redis_cache.main.ssl_port}"
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_key_vault_access_policy.current_user]
}

# Redis primary access key secret
resource "azurerm_key_vault_secret" "redis_primary_access_key" {
  name         = "redis-primary-access-key"
  value        = azurerm_redis_cache.main.primary_access_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_key_vault_access_policy.current_user]
}

# Redis secondary access key secret
resource "azurerm_key_vault_secret" "redis_secondary_access_key" {
  name         = "redis-secondary-access-key"
  value        = azurerm_redis_cache.main.secondary_access_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_key_vault_access_policy.current_user]
}
