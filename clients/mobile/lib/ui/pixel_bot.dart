import 'dart:async';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../session/client_state.dart';

/// Codex Pet atlas — same grid as clients/web/pixel-bot.js
class PixelBot extends StatefulWidget {
  const PixelBot({
    super.key,
    required this.mood,
    required this.petId,
    this.locked = false,
  });

  final ClientState mood;
  final String petId;
  final bool locked;

  static const cellW = 192.0;
  static const cellH = 208.0;

  static const pets = <String, String>{
    'monthly-salary-cat': 'assets/sprites/monthly-salary-cat/spritesheet.webp',
    'arona-v1': 'assets/sprites/arona-v1/spritesheet.webp',
  };

  static const petLabels = <String, String>{
    'monthly-salary-cat': 'Monthly salary cat',
    'arona-v1': 'Arona',
  };

  @override
  State<PixelBot> createState() => _PixelBotState();
}

class _PixelBotState extends State<PixelBot> {
  ui.Image? _sheet;
  int _tick = 0;
  Timer? _timer;

  static const _row = {
    'idle': 0,
    'waving': 3,
    'failed': 5,
    'waiting': 6,
    'review': 8,
  };

  static const _frames = {
    0: 6,
    1: 8,
    2: 8,
    3: 4,
    4: 5,
    5: 8,
    6: 6,
    7: 6,
    8: 6,
  };

  int _moodRow(ClientState m) {
    return switch (m) {
      ClientState.listening => _row['waiting']!,
      ClientState.busy || ClientState.connecting => _row['review']!,
      ClientState.speaking => _row['waving']!,
      ClientState.error || ClientState.offline => _row['failed']!,
      _ => _row['idle']!,
    };
  }

  @override
  void initState() {
    super.initState();
    _load(widget.petId);
    _timer = Timer.periodic(const Duration(milliseconds: 160), (_) {
      if (!mounted) return;
      setState(() => _tick++);
    });
  }

  @override
  void didUpdateWidget(covariant PixelBot oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.petId != widget.petId) {
      _tick = 0;
      _load(widget.petId);
    }
    if (oldWidget.mood != widget.mood) {
      _tick = 0;
    }
  }

  Future<void> _load(String petId) async {
    final path = PixelBot.pets[petId] ?? PixelBot.pets['monthly-salary-cat']!;
    final data = await rootBundle.load(path);
    final codec = await ui.instantiateImageCodec(data.buffer.asUint8List());
    final frame = await codec.getNextFrame();
    if (!mounted) {
      frame.image.dispose();
      return;
    }
    setState(() {
      _sheet?.dispose();
      _sheet = frame.image;
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _sheet?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final phase = (_tick % 2).toDouble();
    Widget sprite = CustomPaint(
      size: const Size(PixelBot.cellW, PixelBot.cellH),
      painter: _SheetPainter(
        sheet: _sheet,
        row: _moodRow(widget.mood),
        tick: _tick,
        frames: _frames,
      ),
    );

    if (widget.mood == ClientState.speaking) {
      sprite = Transform.translate(
        offset: Offset(0, -3 * phase),
        child: sprite,
      );
    } else if (widget.mood == ClientState.listening) {
      sprite = Transform.scale(
        scale: 1 + 0.03 * phase,
        child: sprite,
      );
    }

    return AnimatedOpacity(
      duration: const Duration(milliseconds: 180),
      opacity: widget.locked ? 0.9 : 1,
      child: ColorFiltered(
        colorFilter: widget.locked
            ? const ColorFilter.matrix(<double>[
                0.55, 0.35, 0.1, 0, 0,
                0.55, 0.35, 0.1, 0, 0,
                0.55, 0.35, 0.1, 0, 0,
                0, 0, 0, 0.92, 0,
              ])
            : const ColorFilter.mode(Colors.transparent, BlendMode.dst),
        child: AspectRatio(
          aspectRatio: PixelBot.cellW / PixelBot.cellH,
          child: FittedBox(
            fit: BoxFit.contain,
            child: sprite,
          ),
        ),
      ),
    );
  }
}

class _SheetPainter extends CustomPainter {
  _SheetPainter({
    required this.sheet,
    required this.row,
    required this.tick,
    required this.frames,
  });

  final ui.Image? sheet;
  final int row;
  final int tick;
  final Map<int, int> frames;

  @override
  void paint(Canvas canvas, Size size) {
    final img = sheet;
    if (img == null) return;
    final n = frames[row] ?? 1;
    final col = tick % n;
    final src = Rect.fromLTWH(
      col * PixelBot.cellW,
      row * PixelBot.cellH,
      PixelBot.cellW,
      PixelBot.cellH,
    );
    final dst = Offset.zero & size;
    final paint = Paint()..filterQuality = FilterQuality.none;
    canvas.drawImageRect(img, src, dst, paint);
  }

  @override
  bool shouldRepaint(covariant _SheetPainter old) =>
      old.sheet != sheet || old.row != row || old.tick != tick;
}
