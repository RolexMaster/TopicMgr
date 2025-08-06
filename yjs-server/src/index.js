const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const cors = require('cors');
const helmet = require('helmet');
const { setupWSConnection } = require('y-websocket/bin/utils');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

// 미들웨어 설정
app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// 헬스 체크 엔드포인트
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        service: 'yjs-server',
        version: '1.0.0',
        timestamp: new Date().toISOString()
    });
});

// 서버 정보 엔드포인트
app.get('/api/info', (req, res) => {
    res.json({
        service: 'YJS Collaboration Server',
        version: '1.0.0',
        environment: process.env.NODE_ENV || 'development',
        connections: wss.clients.size
    });
});

// YJS WebSocket 연결 설정
wss.on('connection', setupWSConnection);

// 연결 상태 모니터링
wss.on('connection', (ws, req) => {
    console.log(`새로운 클라이언트 연결: ${req.socket.remoteAddress}`);
    
    ws.on('close', () => {
        console.log('클라이언트 연결 해제');
    });
});

// 에러 핸들링
wss.on('error', (error) => {
    console.error('WebSocket 서버 에러:', error);
});

// 서버 시작
const PORT = process.env.PORT || 1234;
server.listen(PORT, () => {
    console.log(`YJS 서버가 포트 ${PORT}에서 실행 중입니다.`);
    console.log(`헬스 체크: http://localhost:${PORT}/health`);
    console.log(`서버 정보: http://localhost:${PORT}/api/info`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
    console.log('SIGTERM 신호 수신, 서버 종료 중...');
    server.close(() => {
        console.log('서버가 정상적으로 종료되었습니다.');
        process.exit(0);
    });
});

process.on('SIGINT', () => {
    console.log('SIGINT 신호 수신, 서버 종료 중...');
    server.close(() => {
        console.log('서버가 정상적으로 종료되었습니다.');
        process.exit(0);
    });
});