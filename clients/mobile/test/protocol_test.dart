import 'package:flutter_test/flutter_test.dart';

import 'package:agentdock_mobile/protocol/messages.dart';

void main() {
  test('deviceHello encodes type', () {
    final raw = deviceHello(deviceId: 't1', token: 'x');
    expect(raw.contains('"device.hello"'), isTrue);
    expect(raw.contains('"t1"'), isTrue);
    expect(raw.contains('"x"'), isTrue);
  });

  test('decodeJson roundtrip fields', () {
    final m = decodeJson(audioStart('sess'));
    expect(m!['type'], 'audio.start');
    expect(m['payload']['session_id'], 'sess');
  });
}
