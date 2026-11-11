plugins {
    id("com.android.application")
}

layout.buildDirectory.set(rootProject.layout.buildDirectory.dir("gradle/app"))

android {
    namespace = "com.lmqr.ha9_comp_service"
    compileSdk = 35
    buildToolsVersion = "36.0.0"

    defaultConfig {
        applicationId = "com.lmqr.ha9_comp_service"
        minSdk = 35
        targetSdk = 35
        versionCode = 35
        versionName = "15"
    }

    sourceSets {
        named("main") {
            manifest.srcFile("AndroidManifest.xml")
            kotlin.directories += "src"
            res.directories += "res"
        }
        named("debug") {
            manifest.srcFile("standalone/AndroidManifest.xml")
        }
        named("release") {
            manifest.srcFile("standalone/AndroidManifest.xml")
        }
        named("test") {
            kotlin.directories += "test"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    testOptions {
        unitTests.isIncludeAndroidResources = true
    }
}

kotlin {
    compilerOptions {
        freeCompilerArgs.add("-Xjvm-default=all-compatibility")
    }
}

dependencies {
    compileOnly(project(":system-api-stubs"))
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.preference:preference:1.2.1")
    implementation("com.google.android.material:material:1.13.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.16.1")
}
