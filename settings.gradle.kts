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
project(":app").projectDir = file("eink_settings")
project(":system-api-stubs").projectDir = file("tools/android-system-api-stubs")
