// 您可搜索 `env.DB` 将它替换为您的D1绑定的实例
/*
请手动创建以下表：
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  source_ip TEXT,
  event_type TEXT,
  delivered BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS sse_logs (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  ip_address TEXT NOT NULL,
  user_agent TEXT,
  connect_time INTEGER NOT NULL,
  disconnect_time INTEGER,
  status TEXT
);

CREATE TABLE IF NOT EXISTS event_delivery_logs (
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  client_id TEXT NOT NULL,
  delivery_time INTEGER NOT NULL,
  status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_sse_logs_client ON sse_logs(client_id);
CREATE INDEX IF NOT EXISTS idx_delivery_event ON event_delivery_logs(event_id);
*/
async function handleWebhook(request, env) {
    if (request.method !== "POST") {
        return new Response("Method Not Allowed", { status: 405 });
    }

    try {
        const contentType = request.headers.get("content-type");
        if (!contentType?.includes("application/json")) {
            return new Response(JSON.stringify({ error: "Invalid content type" }), {
                status: 400,
                headers: { "Content-Type": "application/json" }
            });
        }

        const payload = await request.json();
        const eventId = `event_${Math.floor(Date.now()/1000)}_${crypto.randomUUID()}`;
        
        // 强制将 payload 转换为纯 JSON 可序列化的对象
        const safePayload = JSON.parse(JSON.stringify(payload));
        const payloadString = JSON.stringify(safePayload);

        // 提取 event_type（确保是字符串）
        let eventType = 'unknown';
        if (payload.event && typeof payload.event === 'string') {
            eventType = payload.event;
        } else if (payload.type) {
            eventType = String(payload.type);
        }

        await env.DB.prepare(
            "INSERT INTO events (id, data, timestamp, source_ip, event_type) VALUES (?, ?, ?, ?, ?)"
        ).bind(
            eventId,
            payloadString,
            Math.floor(Date.now() / 1000),
            request.headers.get('CF-Connecting-IP'),
            eventType  // 确保是字符串
        ).run();

        return new Response(JSON.stringify({ 
            success: true,
            id: eventId,
            timestamp: Math.floor(Date.now() / 1000)
        }), { 
            headers: { "Content-Type": "application/json" } 
        });

    } catch (error) {
        console.error('Webhook处理错误:', error);
        return new Response(JSON.stringify({ 
            success: false,
            error: error.message,
            timestamp: Math.floor(Date.now() / 1000)
        }), { 
            status: 500,
            headers: { "Content-Type": "application/json" } 
        });
    }
}

// SSE处理器
async function handleSSE(request, env) {
    if (request.method !== "GET") {
        return new Response("Method Not Allowed", { status: 405 });
    }

    // 生成客户端ID
    const clientId = request.headers.get('CF-Connecting-IP') || crypto.randomUUID();
    const logId = `log_${Math.floor(Date.now()/1000)}_${crypto.randomUUID()}`;
    const connectTime = Math.floor(Date.now() / 1000);

    // 记录连接日志
    try {
        await env.DB.prepare(
            "INSERT INTO sse_logs (id, client_id, ip_address, user_agent, connect_time, status) VALUES (?, ?, ?, ?, ?, ?)"
        ).bind(
            logId,
            clientId,
            request.headers.get('CF-Connecting-IP'),
            request.headers.get('User-Agent'),
            connectTime,
            'connected'
        ).run();
    } catch (error) {
        console.error("SSE连接日志记录失败:", error);
    }

    const { readable, writable } = new TransformStream();
    const writer = writable.getWriter();
    const encoder = new TextEncoder();

    // 标记事件为已推送并记录日志
    const markEventAsDelivered = async (eventId) => {
        try {
            // 标记事件为已推送
            await env.DB.prepare(
                "UPDATE events SET delivered = TRUE WHERE id = ?"
            ).bind(eventId).run();

            // 记录事件推送日志
            await env.DB.prepare(
                "INSERT INTO event_delivery_logs (id, event_id, client_id, delivery_time, status) VALUES (?, ?, ?, ?, ?)"
            ).bind(
                `delivery_${Math.floor(Date.now()/1000)}_${crypto.randomUUID()}`,
                eventId,
                clientId,
                Math.floor(Date.now() / 1000),
                'delivered'
            ).run();
        } catch (error) {
            console.error("事件标记和日志记录失败:", error);
        }
    };

    // 修改后的sendEvent函数
    const sendEvent = async (eventType, eventData) => {
        const eventPayload = {
            event: eventType,
            id: eventData.id,
            timestamp: Date.now(),
            data: typeof eventData.data === 'string' ? JSON.parse(eventData.data) : eventData.data
        };
        
        await writer.write(encoder.encode(
            `event: ${eventType}\n` +
            `id: ${eventData.id}\n` +
            `data: ${JSON.stringify(eventPayload)}\n\n`
        ));
    };

    // 发送初始历史事件
    const sendInitialEvents = async () => {
        try {
            const { results } = await env.DB.prepare(
                "SELECT id, data, timestamp FROM events WHERE delivered = FALSE ORDER BY timestamp ASC LIMIT 50"
            ).all();
    
            for (const event of results) {
                await sendEvent('message', {  // 统一使用message作为事件类型
                    id: event.id,
                    data: event.data,
                    timestamp: event.timestamp
                });
                await markEventAsDelivered(event.id);
            }
    
            await writer.write(encoder.encode(
                `event: system\n` +
                `data: ${JSON.stringify({
                    type: "init",
                    status: 'ready',
                    count: results.length,
                    timestamp: Date.now()
                })}\n\n`
            ));
        } catch (error) {
            console.error("初始事件发送失败:", error);
        }
    };

    const keepAlive = setInterval(() => {
        writer.write(encoder.encode(
            `event: system\n` +
            `data: ${JSON.stringify({
                type: "heartbeat",
                timestamp: Date.now()
            })}\n\n`
        )).catch(() => {
            clearInterval(keepAlive);
            clearInterval(eventPoller);
        });
    }, 15000);

    // 事件轮询
    let lastTimestamp = Math.floor(Date.now() / 1000);
    const eventPoller = setInterval(async () => {
        try {
            const { results } = await env.DB.prepare(
                "SELECT id, data, timestamp FROM events WHERE timestamp > ? AND delivered = FALSE ORDER BY timestamp ASC"
            ).bind(lastTimestamp).all();
    
            if (results.length > 0) {
                for (const event of results) {
                    await sendEvent('message', {
                        id: event.id,
                        data: event.data,
                        timestamp: event.timestamp
                    });
                    await markEventAsDelivered(event.id);
                    lastTimestamp = event.timestamp;
                }
            }
        } catch (error) {
            console.error("事件轮询错误:", error);
        }
    }, 1000);

    // 清理函数
    const cleanup = async () => {
        clearInterval(keepAlive);
        clearInterval(eventPoller);
        
        // 记录断开连接日志
        try {
            await env.DB.prepare(
                "UPDATE sse_logs SET disconnect_time = ?, status = 'disconnected' WHERE id = ?"
            ).bind(
                Math.floor(Date.now() / 1000),
                logId
            ).run();
        } catch (error) {
            console.error("SSE断开连接日志记录失败:", error);
        }
        
        writer.close();
    };

    // 设置中断监听
    request.signal.addEventListener("abort", cleanup);

    // 发送初始事件
    sendInitialEvents();

    return new Response(readable, {
        headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    });
}

// 清理旧事件
async function cleanupOldEvents(env) {
    try {
        const sevenDaysAgo = Math.floor(Date.now() / 1000) - 604800;
        
        // 清理已推送的旧事件
        const { meta: eventsMeta } = await env.DB.prepare(
            "DELETE FROM events WHERE timestamp < ? AND delivered = TRUE"
        ).bind(sevenDaysAgo).run();
        
        // 清理旧的SSE连接日志（保留最近30天的）
        const thirtyDaysAgo = Math.floor(Date.now() / 1000) - 2592000;
        const { meta: logsMeta } = await env.DB.prepare(
            "DELETE FROM sse_logs WHERE connect_time < ?"
        ).bind(thirtyDaysAgo).run();
        
        // 清理旧的事件推送日志
        const { meta: deliveryMeta } = await env.DB.prepare(
            "DELETE FROM event_delivery_logs WHERE delivery_time < ?"
        ).bind(thirtyDaysAgo).run();
        
        console.log(`清理完成: 
            - 删除${eventsMeta.changes}条旧事件
            - 删除${logsMeta.changes}条SSE连接日志
            - 删除${deliveryMeta.changes}条事件推送日志`);
            
        return {
            events: eventsMeta.changes,
            logs: logsMeta.changes,
            deliveries: deliveryMeta.changes
        };
    } catch (error) {
        console.error('清理错误:', error);
        return {
            events: 0,
            logs: 0,
            deliveries: 0,
            error: error.message
        };
    }
}

// SSE日志查询接口
async function handleSSELogs(request, env) {
    if (request.method !== "GET") {
        return new Response("Method Not Allowed", { status: 405 });
    }

    try {
        const url = new URL(request.url);
        const clientId = url.searchParams.get('client_id');
        const limit = parseInt(url.searchParams.get('limit')) || 50;
        
        let query = "SELECT * FROM sse_logs ORDER BY connect_time DESC LIMIT ?";
        let params = [limit];
        
        if (clientId) {
            query = "SELECT * FROM sse_logs WHERE client_id = ? ORDER BY connect_time DESC LIMIT ?";
            params = [clientId, limit];
        }
        
        const { results } = await env.DB.prepare(query).bind(...params).all();
        
        return new Response(JSON.stringify({ 
            success: true,
            logs: results
        }), { 
            headers: { "Content-Type": "application/json" } 
        });
    } catch (error) {
        console.error('SSE日志查询错误:', error);
        return new Response(JSON.stringify({ 
            success: false,
            error: error.message
        }), { 
            status: 500,
            headers: { "Content-Type": "application/json" } 
        });
    }
}

export default {
    async fetch(request, env) {
        const url = new URL(request.url);
        switch (url.pathname) {
            case "/webhook":
                return handleWebhook(request, env);
            case "/sse":
                return handleSSE(request, env);
            case "/sse/logs":
                return handleSSELogs(request, env);
            default:
                return new Response("Not Found", { status: 404 });
        }
    },

    scheduled: async (event, env, ctx) => {
        ctx.waitUntil(cleanupOldEvents(env));
    }
};
