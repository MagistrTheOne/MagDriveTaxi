# Flutter специфичные правила
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.**  { *; }
-keep class io.flutter.util.**  { *; }
-keep class io.flutter.view.**  { *; }
-keep class io.flutter.**  { *; }
-keep class io.flutter.plugins.**  { *; }

# MapLibre GL правила
-keep class org.maplibre.** { *; }
-keep class com.mapbox.** { *; }

# Geolocator правила
-keep class com.baseflow.geolocator.** { *; }

# WebSocket правила
-keep class io.flutter.plugins.webviewflutter.** { *; }

# Общие правила оптимизации
-optimizations !code/simplification/arithmetic,!code/simplification/cast,!field/*,!class/merging/*
-optimizationpasses 5
-allowaccessmodification
-dontpreverify

# Удаляем неиспользуемые ресурсы
-dontwarn **
-ignorewarnings

# Сохраняем аннотации
-keepattributes *Annotation*
-keepattributes Signature
-keepattributes InnerClasses
-keepattributes EnclosingMethod

# Сохраняем нативные методы
-keepclasseswithmembernames class * {
    native <methods>;
}

# Сохраняем сериализацию
-keepclassmembers class * implements java.io.Serializable {
    static final long serialVersionUID;
    private static final java.io.ObjectStreamField[] serialPersistentFields;
    private void writeObject(java.io.ObjectOutputStream);
    private void readObject(java.io.ObjectInputStream);
    java.lang.Object writeReplace();
    java.lang.Object readResolve();
}
