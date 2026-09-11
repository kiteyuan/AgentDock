import 'dart:async';

import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../session/client_state.dart';
import '../session/device_session.dart';
import 'pixel_bot.dart';
import 'pet_catalog.dart';
import 'theme.dart';

/// Layout aligned with clients/web: centered pet + 3-line reply; tap talk / long-press settings.
class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.session});

  final DeviceSession session;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late final TextEditingController _url;
  late final TextEditingController _token;
  // TTS is a dropdown driven by Runtime tts.list — keep selected id on session.
  final _replyScroll = ScrollController();
  StreamSubscription? _sub;
  bool _holdOpenedSettings = false;
  Timer? _holdTimer;

  DeviceSession get s => widget.session;

  @override
  void initState() {
    super.initState();
    _url = TextEditingController(text: s.url);
    _token = TextEditingController(text: s.token);
    _sub = s.changes.listen((_) {
      if (!mounted) return;
      setState(() {});
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_replyScroll.hasClients) {
          _replyScroll.jumpTo(_replyScroll.position.maxScrollExtent);
        }
      });
    });
    _loadPrefs().then((_) async {
      if (!mounted) return;
      if (s.url.contains('127.0.0.1') || s.url.contains('192.168.') || s.url.contains('100.')) {
        await s.connect();
      } else {
        await _openSettings();
      }
    });
  }

  Future<void> _loadPrefs() async {
    await PetCatalog.ensureLoaded();
    final p = await SharedPreferences.getInstance();
    s.url = p.getString('url') ?? s.url;
    s.token = p.getString('token') ?? '';
    s.ttsId = p.getString('tts') ?? 'haibara';
    s.petId = PetCatalog.resolveId(p.getString('pet'));
    final last = p.getString('reply') ?? '';
    if (last.isNotEmpty && s.replyText.isEmpty) s.replyText = last;
    _url.text = s.url;
    _token.text = s.token;
    setState(() {});
  }

  Future<void> _savePrefs() async {
    final p = await SharedPreferences.getInstance();
    await p.setString('url', s.url);
    await p.setString('token', s.token);
    await p.setString('tts', s.ttsId);
    await p.setString('pet', s.petId);
    await p.setString('reply', s.replyText);
  }

  Future<void> _openSettings() async {
    _url.text = s.url;
    _token.text = s.token;
    await showDialog<void>(
      context: context,
      barrierColor: Colors.black54,
      builder: (ctx) {
        String pet = PetCatalog.resolveId(s.petId);
        String tts = s.ttsId;
        final ttsItems = <DropdownMenuItem<String>>[
          for (final p in s.ttsProviders)
            if ((p['id'] as String? ?? '').isNotEmpty)
              DropdownMenuItem(
                value: p['id'] as String,
                child: Text(
                  p['name'] != null ? '${p['name']} (${p['id']})' : '${p['id']}',
                ),
              ),
        ];
        if (ttsItems.isEmpty) {
          ttsItems.add(DropdownMenuItem(value: tts.isEmpty ? 'haibara' : tts, child: Text(tts.isEmpty ? 'haibara' : tts)));
        }
        if (!ttsItems.any((e) => e.value == tts)) {
          tts = ttsItems.first.value ?? tts;
        }
        return StatefulBuilder(
          builder: (ctx, setLocal) {
            return Dialog(
              backgroundColor: WebUiTheme.panel,
              shape: const RoundedRectangleBorder(
                borderRadius: BorderRadius.zero,
                side: BorderSide(color: WebUiTheme.line, width: 2),
              ),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text('连接', style: TextStyle(color: WebUiTheme.text, fontSize: 16)),
                    const SizedBox(height: 10),
                    _label('Runtime WS'),
                    TextField(
                      controller: _url,
                      style: const TextStyle(color: WebUiTheme.text, fontSize: 13),
                      decoration: const InputDecoration(
                        isDense: true,
                        hintText: 'ws://192.168.x.x:8765',
                        hintStyle: TextStyle(color: WebUiTheme.muted),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.zero,
                          borderSide: BorderSide(color: WebUiTheme.line),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.zero,
                          borderSide: BorderSide(color: WebUiTheme.line),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    _label('Token（可选）'),
                    TextField(
                      controller: _token,
                      obscureText: true,
                      style: const TextStyle(color: WebUiTheme.text, fontSize: 13),
                      decoration: const InputDecoration(
                        isDense: true,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.zero,
                          borderSide: BorderSide(color: WebUiTheme.line),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.zero,
                          borderSide: BorderSide(color: WebUiTheme.line),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    _label('TTS（主机 voices/ + config）'),
                    DropdownButtonFormField<String>(
                      value: tts,
                      dropdownColor: WebUiTheme.panel,
                      style: const TextStyle(color: WebUiTheme.text, fontSize: 13),
                      decoration: const InputDecoration(
                        isDense: true,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.zero,
                          borderSide: BorderSide(color: WebUiTheme.line),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.zero,
                          borderSide: BorderSide(color: WebUiTheme.line),
                        ),
                      ),
                      items: ttsItems,
                      onChanged: (v) {
                        if (v == null) return;
                        setLocal(() => tts = v);
                      },
                    ),
                    const SizedBox(height: 8),
                    _label('角色（主机 pets/ → 本机缓存）'),
                    DropdownButtonFormField<String>(
                      value: pet,
                      dropdownColor: WebUiTheme.panel,
                      style: const TextStyle(color: WebUiTheme.text, fontSize: 13),
                      decoration: const InputDecoration(
                        isDense: true,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.zero,
                          borderSide: BorderSide(color: WebUiTheme.line),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.zero,
                          borderSide: BorderSide(color: WebUiTheme.line),
                        ),
                      ),
                      items: PetCatalog.pets.entries
                          .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value.label)))
                          .toList(),
                      onChanged: (v) {
                        if (v == null) return;
                        setLocal(() => pet = v);
                      },
                    ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        Expanded(
                          child: TextButton(
                            style: TextButton.styleFrom(
                              backgroundColor: WebUiTheme.accent,
                              foregroundColor: const Color(0xFF04140C),
                              shape: const RoundedRectangleBorder(borderRadius: BorderRadius.zero),
                            ),
                            onPressed: () async {
                              s.url = _url.text.trim();
                              s.token = _token.text;
                              s.ttsId = tts.trim().isEmpty ? (s.ttsDefaultId ?? 'haibara') : tts.trim();
                              s.petId = PetCatalog.resolveId(pet);
                              await _savePrefs();
                              if (ctx.mounted) Navigator.pop(ctx);
                              await s.connect();
                            },
                            child: const Text('保存并连接'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextButton(
                            style: TextButton.styleFrom(
                              backgroundColor: const Color(0xFF2A3340),
                              foregroundColor: WebUiTheme.text,
                              shape: const RoundedRectangleBorder(borderRadius: BorderRadius.zero),
                            ),
                            onPressed: () => Navigator.pop(ctx),
                            child: const Text('关闭'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _label(String t) => Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Text(t, style: const TextStyle(color: WebUiTheme.muted, fontSize: 11)),
      );

  Future<void> _onTalk() async {
    final mic = await Permission.microphone.request();
    if (!mic.isGranted) {
      s.lastError = '需要麦克风权限';
      setState(() {});
      return;
    }
    await s.toggleTalk();
    await _savePrefs();
  }

  void _onBotPointerDown() {
    _holdOpenedSettings = false;
    _holdTimer?.cancel();
    _holdTimer = Timer(const Duration(milliseconds: 550), () {
      _holdOpenedSettings = true;
      _openSettings();
    });
  }

  void _onBotPointerUp() {
    _holdTimer?.cancel();
    _holdTimer = null;
  }

  Future<void> _onBotTap() async {
    _holdTimer?.cancel();
    if (_holdOpenedSettings) {
      _holdOpenedSettings = false;
      return;
    }
    if (!s.canToggleTalk) return;
    await _onTalk();
  }

  @override
  void dispose() {
    _holdTimer?.cancel();
    _sub?.cancel();
    _url.dispose();
    _token.dispose();
    _replyScroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reply = s.replyText.trim().isEmpty ? '' : s.replyText;

    return Scaffold(
      backgroundColor: WebUiTheme.bg0,
      body: DecoratedBox(
        decoration: const BoxDecoration(
          color: WebUiTheme.bg0,
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xEB121820), Color(0xFA0A0E12)],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Listener(
                      onPointerDown: (_) => _onBotPointerDown(),
                      onPointerUp: (_) => _onBotPointerUp(),
                      onPointerCancel: (_) => _onBotPointerUp(),
                      child: GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onTap: _onBotTap,
                        onLongPress: _openSettings,
                        child: ConstrainedBox(
                          constraints: BoxConstraints(
                            maxWidth: MediaQuery.sizeOf(context).width * 0.72,
                            maxHeight: MediaQuery.sizeOf(context).height * 0.52,
                          ),
                          child: PixelBot(
                            key: ValueKey('${s.petId}-${s.petsEpoch}'),
                            mood: s.state,
                            petId: s.petId,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    SizedBox(
                      height: WebUiTheme.replyBoxHeight,
                      width: double.infinity,
                      child: GestureDetector(
                        onTap: s.canReplay
                            ? () async {
                                await s.replayLast();
                              }
                            : null,
                        child: SingleChildScrollView(
                          controller: _replyScroll,
                          physics: const ClampingScrollPhysics(),
                          child: Text.rich(
                            TextSpan(
                              children: [
                                TextSpan(
                                  text: reply.isEmpty ? '' : reply,
                                  style: WebUiTheme.replyText,
                                ),
                                if (s.state == ClientState.speaking ||
                                    s.state == ClientState.listening ||
                                    (reply.isEmpty && s.state == ClientState.idle))
                                  WidgetSpan(
                                    alignment: PlaceholderAlignment.baseline,
                                    baseline: TextBaseline.alphabetic,
                                    child: _Caret(
                                      visible: reply.isEmpty || s.state == ClientState.speaking,
                                    ),
                                  ),
                              ],
                            ),
                            textAlign: TextAlign.left,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Caret extends StatefulWidget {
  const _Caret({required this.visible});
  final bool visible;

  @override
  State<_Caret> createState() => _CaretState();
}

class _CaretState extends State<_Caret> with SingleTickerProviderStateMixin {
  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))
      ..repeat();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.visible) return const SizedBox.shrink();
    return AnimatedBuilder(
      animation: _c,
      builder: (context, child) {
        final on = _c.value < 0.5;
        return Opacity(opacity: on ? 1 : 0, child: child);
      },
      child: Container(
        width: 6,
        height: 18,
        margin: const EdgeInsets.only(left: 1),
        color: WebUiTheme.accent,
      ),
    );
  }
}
