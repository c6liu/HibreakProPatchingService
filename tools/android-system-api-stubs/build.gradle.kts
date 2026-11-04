plugins {
    `java-library`
}

layout.buildDirectory.set(rootProject.layout.buildDirectory.dir("gradle/system-api-stubs"))

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
