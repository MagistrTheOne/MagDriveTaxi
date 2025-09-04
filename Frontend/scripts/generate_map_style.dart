import 'dart:io';

void main(List<String> args) async {
  try {
    // Читаем переменные окружения
    final envFile = File('env/env.dev');
    if (!await envFile.exists()) {
      print('❌ Файл env/env.dev не найден');
      exit(1);
    }

    final envContent = await envFile.readAsString();
    final envVars = <String, String>{};
    
    for (final line in envContent.split('\n')) {
      final trimmed = line.trim();
      if (trimmed.isNotEmpty && !trimmed.startsWith('#')) {
        final parts = trimmed.split('=');
        if (parts.length == 2) {
          envVars[parts[0]] = parts[1];
        }
      }
    }

    final apiKey = envVars['MAPTILER_API_KEY'];
    if (apiKey == null || apiKey.isEmpty) {
      print('❌ MAPTILER_API_KEY не найден в env/env.dev');
      exit(1);
    }

    // Читаем шаблон
    final templateFile = File('assets/map/style_dark_gold.tpl.json');
    if (!await templateFile.exists()) {
      print('❌ Шаблон style_dark_gold.tpl.json не найден');
      exit(1);
    }

    final templateContent = await templateFile.readAsString();
    
    // Заменяем плейсхолдеры
    final generatedContent = templateContent.replaceAll('\${MAPTILER_API_KEY}', apiKey);
    
    // Записываем сгенерированный файл
    final outputFile = File('assets/map/style_dark_gold.json');
    await outputFile.writeAsString(generatedContent);
    
    print('✅ Стиль карты сгенерирован: assets/map/style_dark_gold.json');
    print('🔑 Использован API ключ: ${apiKey.substring(0, 8)}...');
    
  } catch (e) {
    print('❌ Ошибка генерации стиля карты: $e');
    exit(1);
  }
}
