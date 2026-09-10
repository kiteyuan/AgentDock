import 'package:flutter_test/flutter_test.dart';

import 'package:agentdock_mobile/main.dart';

void main() {
  testWidgets('AgentDockApp builds', (tester) async {
    await tester.pumpWidget(const AgentDockApp());
    expect(find.textContaining('通话'), findsWidgets);
  });
}
