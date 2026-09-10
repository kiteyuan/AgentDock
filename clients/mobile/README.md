# AgentDock Mobile (Flutter)

正式手机瘦客户端：原生麦克风 + `ws://主机:8765`。  
**不包含** Runtime / STT / TTS / Agent。

## 本机开发

需安装 [Flutter](https://docs.flutter.dev/get-started/install) **≥ 3.27**（`record` / Android 插件依赖 `flutter.compileSdkVersion`）。

```bash
cd clients/mobile
flutter create . --project-name agentdock_mobile --org com.agentdock --platforms=android
# 首次生成 android/ 后，确认 RECORD_AUDIO（见下方）；compileSdk/targetSdk 建议 35
flutter pub get
flutter run
```

设置里填 Runtime，例如 `ws://192.168.1.20:8765`。交互与 Web 一致：**点一下开始录音，再点结束发送**。

## Android 权限

`android/app/src/main/AndroidManifest.xml` 需有：

```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
```

CI 的 `build-android.yml` 会在 `flutter create` 后自动补上。

## 打包

GitHub Actions：`.github/workflows/build-android.yml` → Release APK 附件。

```bash
flutter build apk --release
# 产物：build/app/outputs/flutter-apk/app-release.apk
```

## 目录

```text
lib/
  protocol/   # Device Protocol 编解码
  session/    # WS + 状态机
  audio/      # 录音 WAV / 播 TTS
  ui/         # 点按通话 UI
```
