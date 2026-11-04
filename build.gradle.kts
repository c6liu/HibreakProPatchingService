plugins {
    id("com.android.application") version "9.5.0" apply false
}

providers.gradleProperty("hibreakBuildDir").orNull?.let {
    layout.buildDirectory.set(file(it))
}
