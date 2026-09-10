import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';

class TtsSegment {
  TtsSegment({required this.bytes, this.text = ''});
  final Uint8List bytes;
  final String text;
}

/// Queue sentence-level TTS blobs and play sequentially.
class TtsPlayer {
  final AudioPlayer _player = AudioPlayer();
  final List<TtsSegment> _queue = [];
  bool _playing = false;
  void Function(String text)? onCaption;
  void Function()? onBecameIdle;

  bool get isBusy => _playing || _queue.isNotEmpty;

  void enqueue(TtsSegment seg) {
    if (seg.bytes.isEmpty) return;
    _queue.add(seg);
    unawaited(_pump());
  }

  void clear() {
    _queue.clear();
    unawaited(_player.stop());
    _playing = false;
  }

  Future<void> _pump() async {
    if (_playing) return;
    _playing = true;
    try {
      while (_queue.isNotEmpty) {
        final seg = _queue.removeAt(0);
        onCaption?.call(seg.text);
        final dir = await getTemporaryDirectory();
        final isWav = seg.bytes.length >= 4 &&
            seg.bytes[0] == 0x52 &&
            seg.bytes[1] == 0x49;
        final path =
            '${dir.path}/tts_${DateTime.now().millisecondsSinceEpoch}.${isWav ? 'wav' : 'mp3'}';
        final file = File(path);
        await file.writeAsBytes(seg.bytes, flush: true);
        try {
          final done = Completer<void>();
          late StreamSubscription sub;
          sub = _player.onPlayerComplete.listen((_) {
            if (!done.isCompleted) done.complete();
          });
          await _player.play(DeviceFileSource(path));
          await done.future.timeout(
            const Duration(minutes: 2),
            onTimeout: () {},
          );
          await sub.cancel();
        } finally {
          try {
            await file.delete();
          } catch (_) {}
        }
      }
    } finally {
      _playing = false;
      onBecameIdle?.call();
    }
  }

  Future<void> dispose() async {
    clear();
    await _player.dispose();
  }
}
