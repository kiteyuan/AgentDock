import 'dart:async';
import 'dart:typed_data';

import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../audio/player.dart';
import '../audio/recorder.dart';
import '../protocol/messages.dart' as proto;
import 'client_state.dart';

class DeviceSession {
  DeviceSession({
    required this.deviceId,
    this.deviceType = 'mobile',
  });

  final String deviceId;
  final String deviceType;

  WebSocketChannel? _ws;
  StreamSubscription? _sub;
  Timer? _heartbeat;

  final WavRecorder recorder = WavRecorder();
  final TtsPlayer player = TtsPlayer();

  ClientState state = ClientState.offline;
  String? sessionId;
  String? lastError;
  String statusLine = '';
  String replyText = '';

  String url = 'ws://192.168.1.1:8765';
  String token = '';
  String ttsId = 'haibara';

  final List<int> _ttsBuf = [];
  String _ttsPendingText = '';
  bool _awaitingIdle = false;

  final _changes = StreamController<void>.broadcast();
  Stream<void> get changes => _changes.stream;

  void _notify() {
    if (!_changes.isClosed) _changes.add(null);
  }

  void _setState(ClientState s, {String? status}) {
    state = s;
    if (status != null) statusLine = status;
    _notify();
  }

  Future<void> connect() async {
    await disconnect(silent: true);
    lastError = null;
    _setState(ClientState.connecting, status: url);
    try {
      _ws = IOWebSocketChannel.connect(Uri.parse(url));
      _sub = _ws!.stream.listen(
        _onData,
        onError: (Object e) {
          lastError = e.toString();
          _setState(ClientState.error, status: lastError);
        },
        onDone: () {
          sessionId = null;
          _heartbeat?.cancel();
          _setState(ClientState.offline, status: '未连接');
        },
        cancelOnError: false,
      );
      _ws!.sink.add(proto.deviceHello(
        deviceId: deviceId,
        deviceType: deviceType,
        token: token.isEmpty ? null : token,
        ttsId: ttsId.isEmpty ? null : ttsId,
      ));
      _heartbeat = Timer.periodic(const Duration(seconds: 25), (_) {
        if (_ws != null && sessionId != null) {
          _ws!.sink.add(proto.ping());
        }
      });
      player.onCaption = (t) {
        if (t.trim().isNotEmpty) {
          replyText = replyText.isEmpty ? t.trim() : '$replyText\n${t.trim()}';
          _notify();
        }
      };
      player.onBecameIdle = _maybeIdle;
    } catch (e) {
      lastError = e.toString();
      _setState(ClientState.error, status: lastError);
    }
  }

  Future<void> disconnect({bool silent = false}) async {
    _heartbeat?.cancel();
    _heartbeat = null;
    await _sub?.cancel();
    _sub = null;
    try {
      await _ws?.sink.close();
    } catch (_) {}
    _ws = null;
    sessionId = null;
    player.clear();
    await recorder.cancel();
    if (!silent) {
      _setState(ClientState.offline, status: '未连接');
    }
  }

  Future<void> toggleTalk() async {
    if (state == ClientState.listening) {
      await _stopAndSend();
      return;
    }
    if (state != ClientState.idle || sessionId == null) return;
    await _startListen();
  }

  Future<void> cancelTurn() async {
    if (sessionId == null || _ws == null) return;
    _ws!.sink.add(proto.sessionCancel(sessionId!));
    player.clear();
    _ttsBuf.clear();
    _awaitingIdle = false;
    await recorder.cancel();
    _setState(ClientState.idle, status: '已取消');
  }

  Future<void> _startListen() async {
    try {
      await recorder.start();
      _ttsBuf.clear();
      player.clear();
      _awaitingIdle = false;
      replyText = '';
      _setState(ClientState.listening, status: '正在录音…');
    } catch (e) {
      lastError = e.toString();
      _setState(ClientState.error, status: lastError);
    }
  }

  Future<void> _stopAndSend() async {
    final bytes = await recorder.stop();
    if (bytes == null || bytes.isEmpty || _ws == null || sessionId == null) {
      _setState(ClientState.idle, status: '空录音');
      return;
    }
    _setState(ClientState.busy, status: '识别中…');
    _ws!.sink.add(proto.audioStart(sessionId!));
    const chunk = 4096;
    for (var i = 0; i < bytes.length; i += chunk) {
      final end = (i + chunk < bytes.length) ? i + chunk : bytes.length;
      _ws!.sink.add(bytes.sublist(i, end));
    }
    _ws!.sink.add(proto.audioEnd(sessionId!));
  }

  void _onData(dynamic data) {
    if (data is List<int>) {
      _ttsBuf.addAll(data);
      return;
    }
    if (data is! String) return;
    final m = proto.decodeJson(data);
    if (m == null) return;
    final type = m['type'] as String? ?? '';
    final payload = (m['payload'] is Map)
        ? Map<String, dynamic>.from(m['payload'] as Map)
        : <String, dynamic>{};

    switch (type) {
      case 'session.accept':
        sessionId = payload['session_id'] as String?;
        _setState(ClientState.idle, status: '点按通话');
        if (ttsId.isNotEmpty && sessionId != null) {
          _ws?.sink.add(proto.ttsSelect(sessionId!, ttsId));
        }
        break;
      case 'error':
        lastError = '${payload['detail'] ?? payload['message'] ?? 'error'}';
        _setState(ClientState.error, status: lastError);
        break;
      case 'stt.final':
        final t = (payload['text'] as String? ?? '').trim();
        if (t.isNotEmpty) {
          statusLine = '你：$t';
          replyText = t;
        }
        _setState(ClientState.busy, status: statusLine);
        break;
      case 'agent.thinking':
      case 'agent.tool_call':
      case 'agent.tool_result':
        if (type == 'agent.tool_call') {
          statusLine = '工具：${payload['tool'] ?? 'tool'}';
        } else if (type == 'agent.tool_result') {
          statusLine = '结果：${payload['status'] ?? 'ok'}';
        } else {
          statusLine = '思考中';
        }
        _setState(ClientState.busy, status: statusLine);
        break;
      case 'agent.message':
        final speak = payload['speak'] != false;
        final t = (payload['content'] ?? payload['text'] ?? '').toString().trim();
        if (!speak && t.isNotEmpty) {
          replyText = t;
        }
        _setState(ClientState.busy, status: '处理中');
        break;
      case 'tts.start':
        _ttsBuf.clear();
        _ttsPendingText = (payload['text'] as String? ?? '').trim();
        _setState(ClientState.speaking, status: '播放中');
        break;
      case 'tts.end':
        if (_ttsBuf.isNotEmpty) {
          player.enqueue(TtsSegment(
            bytes: Uint8List.fromList(_ttsBuf),
            text: _ttsPendingText,
          ));
          _ttsBuf.clear();
          _ttsPendingText = '';
        }
        break;
      case 'agent.done':
        _awaitingIdle = true;
        _maybeIdle();
        break;
      case 'agent.cancel':
        player.clear();
        _ttsBuf.clear();
        _awaitingIdle = false;
        _setState(ClientState.idle, status: '已取消');
        break;
      case 'device.pong':
        break;
      default:
        break;
    }
  }

  void _maybeIdle() {
    if (_awaitingIdle && !player.isBusy && _ttsBuf.isEmpty) {
      _awaitingIdle = false;
      if (state == ClientState.busy || state == ClientState.speaking) {
        _setState(ClientState.idle, status: '点按通话');
      }
    }
  }

  Future<void> dispose() async {
    await disconnect(silent: true);
    await recorder.dispose();
    await player.dispose();
    await _changes.close();
  }
}
