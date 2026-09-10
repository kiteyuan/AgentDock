import 'package:flutter/material.dart';

/// Colors / layout tokens aligned with clients/web/styles.css
abstract final class WebUiTheme {
  static const bg0 = Color(0xFF0A0E12);
  static const text = Color(0xFFC8D0D8);
  static const muted = Color(0xFF6A7684);
  static const accent = Color(0xFF3ECF8E);
  static const panel = Color(0xFF0D1218);
  static const line = Color(0xFF243040);

  static const replySize = 24.0;
  static const replyLh = 1.25;
  static const replyLines = 3;

  static double get replyBoxHeight => replySize * replyLh * replyLines;

  static const uiText = TextStyle(
    color: text,
    fontSize: 12,
    height: 1.25,
    fontFamily: 'monospace',
  );

  static const replyText = TextStyle(
    color: text,
    fontSize: replySize,
    height: replyLh,
    fontFamily: 'monospace',
  );
}
