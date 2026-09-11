import 'package:flutter_test/flutter_test.dart';

import 'package:agentdock_mobile/main.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('AgentDockApp builds web-aligned stage', (tester) async {
    await tester.pumpWidget(const AgentDockApp(deviceId: 'test-device'));
    await tester.pump();
    expect(find.byType(AgentDockApp), findsOneWidget);
  });
}
