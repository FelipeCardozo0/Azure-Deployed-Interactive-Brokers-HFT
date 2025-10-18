# Incident Response Runbook

## Overview
This runbook provides step-by-step procedures for handling incidents in the HFT trading system.

## Incident Severity Levels

### P1 - Critical
- System down or major functionality unavailable
- Data loss or corruption
- Security breach
- Financial impact > $10,000

### P2 - High
- Significant performance degradation
- Partial system unavailability
- Financial impact $1,000 - $10,000

### P3 - Medium
- Minor performance issues
- Non-critical feature unavailable
- Financial impact < $1,000

### P4 - Low
- Cosmetic issues
- Documentation updates
- No financial impact

## Incident Response Process

### 1. Initial Response (0-15 minutes)

#### Immediate Actions
1. **Assess the situation**
   - Check system status dashboard
   - Review recent deployments
   - Check for external factors (market hours, IB Gateway status)

2. **Activate kill switch if needed**
   ```bash
   # Via API
   curl -X POST "https://api.trading.example.com/api/v1/kill_switch" \
        -H "Content-Type: application/json" \
        -d '{"active": true, "reason": "Incident response"}'
   
   # Via kubectl
   kubectl exec -n trading deployment/api -- python -c "
   import requests
   requests.post('http://localhost:8000/api/v1/kill_switch', 
                 json={'active': True, 'reason': 'Incident response'})
   "
   ```

3. **Check system health**
   ```bash
   # Check all pods
   kubectl get pods -n trading
   
   # Check logs
   kubectl logs -n trading deployment/ib-gateway --tail=100
   kubectl logs -n trading deployment/md-collector --tail=100
   kubectl logs -n trading deployment/strategy --tail=100
   kubectl logs -n trading deployment/risk-oms --tail=100
   kubectl logs -n trading deployment/api --tail=100
   ```

4. **Check database connectivity**
   ```bash
   # Test PostgreSQL connection
   kubectl exec -n trading deployment/api -- python -c "
   import asyncpg
   import asyncio
   async def test():
       conn = await asyncpg.connect('postgresql://...')
       await conn.close()
   asyncio.run(test())
   "
   
   # Test Redis connection
   kubectl exec -n trading deployment/api -- python -c "
   import redis
   r = redis.from_url('redis://...')
   r.ping()
   "
   ```

### 2. Investigation (15-60 minutes)

#### System Diagnostics
1. **Check resource usage**
   ```bash
   # CPU and memory usage
   kubectl top pods -n trading
   
   # Node resource usage
   kubectl top nodes
   ```

2. **Check network connectivity**
   ```bash
   # Test IB Gateway connectivity
   kubectl exec -n trading deployment/md-collector -- nc -zv ib-gateway 7497
   
   # Test database connectivity
   kubectl exec -n trading deployment/api -- nc -zv postgres-server 5432
   
   # Test Redis connectivity
   kubectl exec -n trading deployment/api -- nc -zv redis-server 6379
   ```

3. **Check application metrics**
   ```bash
   # Prometheus metrics
   curl http://api.trading.example.com/metrics
   
   # Application Insights
   # Check Azure portal for Application Insights data
   ```

4. **Check logs for errors**
   ```bash
   # Search for errors in logs
   kubectl logs -n trading deployment/strategy | grep -i error
   kubectl logs -n trading deployment/risk-oms | grep -i error
   kubectl logs -n trading deployment/md-collector | grep -i error
   ```

#### Data Integrity Checks
1. **Check market data flow**
   ```bash
   # Verify market data is being received
   kubectl exec -n trading deployment/md-collector -- python -c "
   import redis
   r = redis.from_url('redis://...')
   print('Market data keys:', r.keys('market_data:*'))
   "
   ```

2. **Check order flow**
   ```bash
   # Verify orders are being processed
   kubectl exec -n trading deployment/risk-oms -- python -c "
   import redis
   r = redis.from_url('redis://...')
   print('Order queue length:', r.llen('order_queue'))
   "
   ```

3. **Check database integrity**
   ```sql
   -- Connect to PostgreSQL and run integrity checks
   SELECT COUNT(*) FROM ticks WHERE timestamp > NOW() - INTERVAL '1 hour';
   SELECT COUNT(*) FROM bars WHERE timestamp > NOW() - INTERVAL '1 hour';
   SELECT COUNT(*) FROM orders WHERE created_at > NOW() - INTERVAL '1 hour';
   SELECT COUNT(*) FROM fills WHERE created_at > NOW() - INTERVAL '1 hour';
   ```

### 3. Resolution (1-4 hours)

#### Common Resolution Steps

1. **Restart affected services**
   ```bash
   # Restart specific deployment
   kubectl rollout restart deployment/strategy -n trading
   kubectl rollout restart deployment/risk-oms -n trading
   kubectl rollout restart deployment/md-collector -n trading
   
   # Wait for rollout to complete
   kubectl rollout status deployment/strategy -n trading
   kubectl rollout status deployment/risk-oms -n trading
   kubectl rollout status deployment/md-collector -n trading
   ```

2. **Scale services if needed**
   ```bash
   # Scale up services
   kubectl scale deployment strategy --replicas=3 -n trading
   kubectl scale deployment risk-oms --replicas=3 -n trading
   kubectl scale deployment md-collector --replicas=3 -n trading
   ```

3. **Clear caches if needed**
   ```bash
   # Clear Redis cache
   kubectl exec -n trading deployment/api -- python -c "
   import redis
   r = redis.from_url('redis://...')
   r.flushdb()
   "
   ```

4. **Restart IB Gateway if needed**
   ```bash
   # Restart IB Gateway
   kubectl rollout restart deployment/ib-gateway -n trading
   
   # Wait for restart
   kubectl rollout status deployment/ib-gateway -n trading
   ```

#### Database Issues
1. **Check database connections**
   ```bash
   # Check active connections
   kubectl exec -n trading deployment/api -- python -c "
   import asyncpg
   import asyncio
   async def check():
       conn = await asyncpg.connect('postgresql://...')
       result = await conn.fetch('SELECT * FROM pg_stat_activity')
       print(f'Active connections: {len(result)}')
       await conn.close()
   asyncio.run(check())
   "
   ```

2. **Check database performance**
   ```sql
   -- Check slow queries
   SELECT query, mean_time, calls 
   FROM pg_stat_statements 
   ORDER BY mean_time DESC 
   LIMIT 10;
   
   -- Check table sizes
   SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
   FROM pg_tables 
   WHERE schemaname = 'public'
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
   ```

#### Network Issues
1. **Check network policies**
   ```bash
   # Check network policies
   kubectl get networkpolicies -n trading
   
   # Check service endpoints
   kubectl get endpoints -n trading
   ```

2. **Test network connectivity**
   ```bash
   # Test internal connectivity
   kubectl exec -n trading deployment/strategy -- ping ib-gateway
   kubectl exec -n trading deployment/strategy -- ping postgres-server
   kubectl exec -n trading deployment/strategy -- ping redis-server
   ```

### 4. Recovery (1-2 hours)

#### Post-Incident Actions
1. **Verify system functionality**
   ```bash
   # Check all services are running
   kubectl get pods -n trading
   
   # Check health endpoints
   curl http://api.trading.example.com/api/v1/health
   curl http://api.trading.example.com/api/v1/health/detailed
   ```

2. **Test trading functionality**
   ```bash
   # Test market data flow
   kubectl exec -n trading deployment/md-collector -- python -c "
   # Test market data collection
   "
   
   # Test signal generation
   kubectl exec -n trading deployment/strategy -- python -c "
   # Test signal generation
   "
   
   # Test order processing
   kubectl exec -n trading deployment/risk-oms -- python -c "
   # Test order processing
   "
   ```

3. **Deactivate kill switch if activated**
   ```bash
   # Via API
   curl -X POST "https://api.trading.example.com/api/v1/kill_switch" \
        -H "Content-Type: application/json" \
        -d '{"active": false, "reason": "System recovered"}'
   ```

4. **Monitor system for stability**
   ```bash
   # Monitor logs for errors
   kubectl logs -n trading deployment/strategy --follow
   kubectl logs -n trading deployment/risk-oms --follow
   kubectl logs -n trading deployment/md-collector --follow
   ```

### 5. Post-Incident Review

#### Documentation
1. **Incident report**
   - Incident description
   - Root cause analysis
   - Resolution steps
   - Timeline of events
   - Lessons learned
   - Prevention measures

2. **Update runbooks**
   - Add new resolution steps
   - Update troubleshooting procedures
   - Improve monitoring

3. **System improvements**
   - Implement additional monitoring
   - Improve alerting
   - Enhance documentation
   - Update procedures

## Emergency Contacts

### On-Call Team
- **Primary**: [Name] - [Phone] - [Email]
- **Secondary**: [Name] - [Phone] - [Email]
- **Escalation**: [Name] - [Phone] - [Email]

### External Contacts
- **Interactive Brokers**: [Phone] - [Email]
- **Azure Support**: [Phone] - [Email]
- **Database Support**: [Phone] - [Email]

## Escalation Procedures

### P1 Incidents
1. **Immediate escalation** to on-call team
2. **Notify management** within 15 minutes
3. **External escalation** if not resolved within 1 hour

### P2 Incidents
1. **Notify on-call team** within 30 minutes
2. **Management notification** if not resolved within 2 hours

### P3/P4 Incidents
1. **Standard procedures** apply
2. **Management notification** if not resolved within 4 hours

## Recovery Time Objectives (RTO)

- **P1**: 15 minutes
- **P2**: 1 hour
- **P3**: 4 hours
- **P4**: 24 hours

## Recovery Point Objectives (RPO)

- **Market Data**: 1 second
- **Order Data**: 1 second
- **Position Data**: 1 second
- **Historical Data**: 1 hour
