pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "HiBreakProPatchingService"
include(":app", ":system-api-stubs")
project(":app").projectDir = file("a9_accessibility_service")
project(":system-api-stubs").projectDir = file("tools/android-system-api-stubs")
