import 'package:flutter/material.dart';

import 'session/device_session.dart';
import 'ui/home_page.dart';
import 'ui/theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AgentDockApp());
}

class AgentDockApp extends StatefulWidget {
  const AgentDockApp({super.key});

  @override
  State<AgentDockApp> createState() => _AgentDockAppState();
}

class _AgentDockAppState extends State<AgentDockApp> {
  late final DeviceSession _session;

  @override
  void initState() {
    super.initState();
    _session = DeviceSession(deviceId: 'mobile-flutter-001');
  }

  @override
  void dispose() {
    _session.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AgentDock',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: WebUiTheme.bg0,
        colorScheme: ColorScheme.fromSeed(
          seedColor: WebUiTheme.accent,
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: HomePage(session: _session),
    );
  }
}
