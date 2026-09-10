import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../session/client_state.dart';
import '../session/device_session.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.session});

  final DeviceSession session;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late final TextEditingController _url;
  late final TextEditingController _token;
  late final TextEditingController _tts;
  bool _settingsOpen = false;

  DeviceSession get s => widget.session;

  @override
  void initState() {
    super.initState();
    _url = TextEditingController(text: s.url);
    _token = TextEditingController(text: s.token);
    _tts = TextEditingController(text: s.ttsId);
    s.changes.listen((_) {
      if (mounted) setState(() {});
    });
    _loadPrefs().then((_) {
      if (s.url.isNotEmpty) s.connect();
    });
  }

  Future<void> _loadPrefs() async {
    final p = await SharedPreferences.getInstance();
    s.url = p.getString('url') ?? s.url;
    s.token = p.getString('token') ?? '';
    s.ttsId = p.getString('tts') ?? 'haibara';
    _url.text = s.url;
    _token.text = s.token;
    _tts.text = s.ttsId;
    setState(() {});
  }

  Future<void> _savePrefs() async {
    final p = await SharedPreferences.getInstance();
    await p.setString('url', s.url);
    await p.setString('token', s.token);
    await p.setString('tts', s.ttsId);
  }

  Future<void> _applySettings() async {
    s.url = _url.text.trim();
    s.token = _token.text;
    s.ttsId = _tts.text.trim().isEmpty ? 'haibara' : _tts.text.trim();
    await _savePrefs();
    setState(() => _settingsOpen = false);
    await s.connect();
  }

  Future<void> _onTalk() async {
    final mic = await Permission.microphone.request();
    if (!mic.isGranted) {
      s.lastError = '需要麦克风权限';
      setState(() {});
      return;
    }
    await s.toggleTalk();
  }

  Color _moodColor(ClientState st) => switch (st) {
        ClientState.listening => const Color(0xFF2F7FD1),
        ClientState.busy => const Color(0xFFC9A227),
        ClientState.speaking => const Color(0xFF2F9E6B),
        ClientState.error => const Color(0xFFD45B5B),
        ClientState.idle => const Color(0xFF3A7A5C),
        _ => const Color(0xFF5A6570),
      };

  @override
  void dispose() {
    _url.dispose();
    _token.dispose();
    _tts.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final accent = _moodColor(s.state);
    return Scaffold(
      backgroundColor: const Color(0xFF0A0C0F),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          child: Column(
            children: [
              Row(
                children: [
                  IconButton(
                    onPressed: () => setState(() => _settingsOpen = !_settingsOpen),
                    icon: const Icon(Icons.settings, color: Color(0xFF7A8796)),
                  ),
                  const Spacer(),
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: s.sessionId != null ? accent : const Color(0xFF3A4450),
                    ),
                  ),
                ],
              ),
              if (_settingsOpen) _settingsPanel(),
              const SizedBox(height: 8),
              Text(
                s.state.label,
                style: TextStyle(
                  color: accent,
                  fontSize: 18,
                  letterSpacing: 1.2,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                s.statusLine.isEmpty ? '—' : s.statusLine,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: Color(0xFF7A8796), fontSize: 13),
              ),
              const SizedBox(height: 16),
              Expanded(
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFF12161C),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: const Color(0xFF1E2630)),
                  ),
                  child: SingleChildScrollView(
                    child: Text(
                      s.replyText.isEmpty ? '点按下方按钮说话' : s.replyText,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Color(0xFFEEF2F6),
                        fontSize: 18,
                        height: 1.45,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              GestureDetector(
                onTap: s.state.canToggleTalk ? _onTalk : null,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  width: 148,
                  height: 148,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: s.state == ClientState.listening
                        ? const Color(0xFFD45B5B)
                        : accent.withValues(alpha: s.state.canToggleTalk ? 1 : 0.35),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.45),
                        blurRadius: 18,
                        offset: const Offset(0, 8),
                      ),
                    ],
                  ),
                  child: Text(
                    s.state == ClientState.listening ? '结束' : '通话',
                    style: const TextStyle(
                      color: Color(0xFF04140C),
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 4,
                    ),
                  ),
                ),
              ),
              if (s.state == ClientState.busy || s.state == ClientState.speaking)
                TextButton(
                  onPressed: s.cancelTurn,
                  child: const Text('取消', style: TextStyle(color: Color(0xFF7A8796))),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _settingsPanel() {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF12161C),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Runtime WS', style: TextStyle(color: Color(0xFF7A8796), fontSize: 12)),
          TextField(
            controller: _url,
            style: const TextStyle(color: Colors.white),
            decoration: const InputDecoration(
              hintText: 'ws://192.168.x.x:8765',
              hintStyle: TextStyle(color: Color(0xFF5A6570)),
              border: InputBorder.none,
            ),
          ),
          const Text('Token（可选）', style: TextStyle(color: Color(0xFF7A8796), fontSize: 12)),
          TextField(
            controller: _token,
            obscureText: true,
            style: const TextStyle(color: Colors.white),
            decoration: const InputDecoration(border: InputBorder.none),
          ),
          const Text('TTS', style: TextStyle(color: Color(0xFF7A8796), fontSize: 12)),
          TextField(
            controller: _tts,
            style: const TextStyle(color: Colors.white),
            decoration: const InputDecoration(border: InputBorder.none),
          ),
          const SizedBox(height: 8),
          FilledButton(
            onPressed: _applySettings,
            style: FilledButton.styleFrom(backgroundColor: const Color(0xFF2F9E6B)),
            child: const Text('保存并连接'),
          ),
        ],
      ),
    );
  }
}
