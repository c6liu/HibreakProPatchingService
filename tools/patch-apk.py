from pathlib import Path
import argparse
import re
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description="Patch the tested vbbot APK after apktool decoding")
parser.add_argument("decoded_apk", type=Path)
B = parser.parse_args().decoded_apk
S = B / "smali/com/lmqr/ha9_comp_service"
REPO = Path(__file__).resolve().parent.parent / "a9_accessibility_service"
A = "{http://schemas.android.com/apk/res/android}"
ET.register_namespace("android", A[1:-1])
ET.register_namespace("app", "http://schemas.android.com/apk/res-auto")


def xml(path, edit):
    tree = ET.parse(path)
    edit(tree.getroot())
    tree.write(path, encoding="utf-8", xml_declaration=True)


def replace(path, old, new, count=1):
    text = path.read_text()
    assert text.count(old) == count, (path, old, text.count(old))
    path.write_text(text.replace(old, new))


def add_public(root, kind, name):
    ids = [int(e.get("id"), 16) for e in root if e.get("type") == kind]
    value = max(ids) + 1
    ET.SubElement(root, "public", type=kind, name=name, id=f"0x{value:08x}")
    return value


public = ET.parse(B / "res/values/public.xml")
button_id = add_public(public.getroot(), "id", "button5")
toolbar_id = add_public(public.getroot(), "id", "settings_toolbar")
per_app_xml_id = add_public(public.getroot(), "xml", "per_app_preferences")
refresh_array_ids = {
    name: public.getroot().find(f"public[@type='array'][@name='{name}']").get("id")
    for name in ("refresh_options", "refresh_values")
}
add_public(public.getroot(), "style", "Theme.Ha9_comp_service.Settings")
for name in ("regal", "fast", "hd", "extreme", "hyper"):
    add_public(public.getroot(), "string", name)
public.write(B / "res/values/public.xml", encoding="utf-8", xml_declaration=True)


def strings(root):
    root.find("string[@name='title_activity_settings']").text = "E-Ink Settings"
    for name, label in zip(("regal", "fast", "hd", "extreme", "hyper"),
                           ("Regal", "Fast", "HD", "Extreme", "Hyper")):
        ET.SubElement(root, "string", name=name).text = label


xml(B / "res/values/strings.xml", strings)


def arrays(root):
    options = root.find("string-array[@name='refresh_options']")
    options.clear()
    options.set("name", "refresh_options")
    for name in ("hd", "regal", "fast", "extreme", "hyper"):
        ET.SubElement(options, "item").text = f"@string/{name}"
    values = root.find("string-array[@name='refresh_values']")
    values.clear()
    values.set("name", "refresh_values")
    for value in ("2", "0", "1", "3", "4"):
        ET.SubElement(values, "item").text = value


xml(B / "res/values/arrays.xml", arrays)


def menu(root):
    row = root.find(f".//*[@{A}id='@id/linear_layout']")
    for button, name in zip(row, ("hd", "regal", "fast", "extreme")):
        button.set(A + "text", f"@string/{name}")
        button.set(A + "layout_marginEnd", "5dp")
    fifth = ET.SubElement(row, "Button", dict(row[-1].attrib))
    fifth.set(A + "id", "@id/button5")
    fifth.set(A + "text", "@string/hyper")
    del fifth.attrib[A + "layout_marginEnd"]
    # The stock warm/cold light icons are reversed on the HiBreak Pro.
    for container, icon in (("light_seekbar_container", "baseline_brightness_high_24_dark"),
                            ("light_warm_seekbar_container", "baseline_moon_24")):
        image = root.find(f".//*[@{A}id='@id/{container}']/ImageView")
        image.set(A + "src", f"@drawable/{icon}")


xml(B / "res/layout/floating_menu_layout.xml", menu)
(B / "res/layout/settings_activity.xml").write_text(
    (REPO / "res/layout/settings_activity.xml").read_text())


def styles(root):
    style = ET.SubElement(root, "style", name="Theme.Ha9_comp_service.Settings",
                          parent="@style/Theme.Ha9_comp_service")
    ET.SubElement(style, "item", name="windowActionBar").text = "false"
    ET.SubElement(style, "item", name="windowNoTitle").text = "true"
    ET.SubElement(style, "item", name="android:windowLightStatusBar").text = "?attr/isLightTheme"


xml(B / "res/values/styles.xml", styles)


def manifest(root):
    root.attrib.pop(A + "sharedUserId", None)
    activity = root.find(f"application/activity[@{A}name='.SettingsActivity']")
    if activity is None:
        activity = root.find(f"application/activity[@{A}name='com.lmqr.ha9_comp_service.SettingsActivity']")
    assert activity is not None
    activity.set(A + "theme", "@style/Theme.Ha9_comp_service.Settings")


xml(B / "AndroidManifest.xml", manifest)
prefs = B / "res/xml/root_preferences.xml"
prefs.write_text((REPO / "res/xml/root_preferences.xml").read_text())
(B / "res/xml/per_app_preferences.xml").write_text(
    (REPO / "res/xml/per_app_preferences.xml").read_text())

enum = S / "RefreshMode.smali"
replace(enum, ".field public static final enum SPEED:",
        ".field public static final enum HYPER:Lcom/lmqr/ha9_comp_service/RefreshMode;\n\n"
        ".field public static final enum SPEED:")
replace(enum, ".locals 4\n\n    .line 0", ".locals 5\n\n    .line 0")
replace(enum, "    filled-new-array {v0, v1, v2, v3},",
        "    sget-object v4, Lcom/lmqr/ha9_comp_service/RefreshMode;->HYPER:Lcom/lmqr/ha9_comp_service/RefreshMode;\n\n"
        "    filled-new-array {v0, v1, v2, v3, v4},")
replace(enum, "    invoke-static {}, Lcom/lmqr/ha9_comp_service/RefreshMode;->$values()",
        """    new-instance v0, Lcom/lmqr/ha9_comp_service/RefreshMode;
    const/4 v1, 0x4
    const-string v2, "h"
    const-string v3, "HYPER"
    invoke-direct {v0, v3, v1, v2, v1}, Lcom/lmqr/ha9_comp_service/RefreshMode;-><init>(Ljava/lang/String;ILjava/lang/String;I)V
    sput-object v0, Lcom/lmqr/ha9_comp_service/RefreshMode;->HYPER:Lcom/lmqr/ha9_comp_service/RefreshMode;

    invoke-static {}, Lcom/lmqr/ha9_comp_service/RefreshMode;->$values()""")

accessor = S / "FloatingMenuViewAccessor.smali"
text = accessor.read_text()
field = ".field private final button4:Landroid/widget/Button;"
text = text.replace(field, field + "\n\n" + field.replace("button4", "button5"))
start = text.index("    const v0, 0x7f090075")
end = text.index("\n    const v0,", start + 10)
block = text[start:end]
text = text[:end] + "\n" + block.replace("0x7f090075", hex(button_id)).replace(
    "button4", "button5") + text[end:]
getter = re.search(r"\.method public final getButton4\(\).*?\.end method", text, re.S).group()
text += "\n" + getter.replace("getButton4", "getButton5").replace("button4", "button5") + "\n"
accessor.write_text(text)

listener = S / "A9AccessibilityService$openFloatingMenu$2$1$5.smali"
new_listener = "A9AccessibilityService$HyperClick"
(S / f"{new_listener}.smali").write_text(listener.read_text().replace(
    "A9AccessibilityService$openFloatingMenu$2$1$5", new_listener).replace(
    "->SPEED:", "->HYPER:"))
for suffix, old_mode, new_mode in (
        ("2", "CLEAR", "SMOOTH"),
        ("3", "BALANCED", "CLEAR"),
        ("4", "SMOOTH", "BALANCED")):
    replace(S / f"A9AccessibilityService$openFloatingMenu$2$1${suffix}.smali",
            f"->{old_mode}:", f"->{new_mode}:")

service = S / "A9AccessibilityService.smali"
text = service.read_text()
start = text.index("    invoke-virtual {v8}, Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;->getButton4()")
end = text.index("    invoke-virtual {v6, v9}, Landroid/widget/Button;->setOnClickListener", start)
end = text.index("\n", end) + 1
text = text[:end] + "\n" + text[start:end].replace("getButton4", "getButton5").replace(
    "A9AccessibilityService$openFloatingMenu$2$1$5", new_listener) + text[end:]
old = '''    const-string v1, "EINK_REFRESH_SPEED_FAST"

    invoke-virtual {v0, v1}, Landroid/content/IntentFilter;->addAction(Ljava/lang/String;)V'''
assert text.count(old) == 1
text = text.replace(old, old + "\n\n" + old.replace("SPEED_FAST", "SPEED_HYPER"))
service.write_text(text)

view = S / "ViewAccessorKt.smali"
text = view.read_text()
signature = ".method public static final updateButtons(Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;Lcom/lmqr/ha9_comp_service/RefreshMode;)Lkotlin/Unit;"
start = text.index(signature)
end = text.index(".end method", start) + len(".end method")
method = signature + "\n    .locals 3\n    if-eqz p0, :done\n"
for i in range(1, 6):
    method += f"""
    invoke-virtual {{p0}}, Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;->getButton{i}()Landroid/widget/Button;
    move-result-object v0
    invoke-static {{v0}}, Lcom/lmqr/ha9_comp_service/A9AccessibilityServiceKt;->deselect(Landroid/widget/Button;)V
"""
for i, name in enumerate(("SMOOTH", "CLEAR", "BALANCED", "SPEED", "HYPER"), 1):
    method += f"""
    sget-object v1, Lcom/lmqr/ha9_comp_service/RefreshMode;->{name}:Lcom/lmqr/ha9_comp_service/RefreshMode;
    if-ne p1, v1, :next{i}
    invoke-virtual {{p0}}, Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;->getButton{i}()Landroid/widget/Button;
    move-result-object v0
    invoke-static {{v0}}, Lcom/lmqr/ha9_comp_service/A9AccessibilityServiceKt;->select(Landroid/widget/Button;)V
    goto :done
    :next{i}
"""
method += """
    :done
    sget-object v0, Lkotlin/Unit;->INSTANCE:Lkotlin/Unit;
    return-object v0
.end method"""
view.write_text(text[:start] + method + text[end:])

receiver = S / "A9AccessibilityService$receiverEink$1.smali"
replace(receiver, "    invoke-virtual {p1}, Ljava/lang/String;->hashCode()I", """
    const-string v1, "EINK_REFRESH_SPEED_HYPER"
    invoke-virtual {p1, v1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v1
    if-eqz v1, :not_hyper
    iget-object p0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService$receiverEink$1;->this$0:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    invoke-static {p0}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->access$getRefreshModeManager$p(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)Lcom/lmqr/ha9_comp_service/RefreshModeManager;
    move-result-object p0
    sget-object v1, Lcom/lmqr/ha9_comp_service/RefreshMode;->HYPER:Lcom/lmqr/ha9_comp_service/RefreshMode;
    invoke-virtual {p0, v1}, Lcom/lmqr/ha9_comp_service/RefreshModeManager;->changeMode(Lcom/lmqr/ha9_comp_service/RefreshMode;)V
    return-void
    :not_hyper
    invoke-virtual {p1}, Ljava/lang/String;->hashCode()I""")

replace(S / "SettingsActivity.smali",
        "    if-nez p1, :cond_0",
        f"""    const v0, {hex(toolbar_id)}
    invoke-virtual {{p0, v0}}, Landroidx/appcompat/app/AppCompatActivity;->findViewById(I)Landroid/view/View;
    move-result-object v0
    check-cast v0, Landroidx/appcompat/widget/Toolbar;
    new-instance v1, Lcom/lmqr/ha9_comp_service/SettingsBackClick;
    invoke-direct {{v1, p0}}, Lcom/lmqr/ha9_comp_service/SettingsBackClick;-><init>(Landroid/app/Activity;)V
    invoke-virtual {{v0, v1}}, Landroidx/appcompat/widget/Toolbar;->setNavigationOnClickListener(Landroid/view/View$OnClickListener;)V

    if-nez p1, :cond_0""")
(S / "SettingsBackClick.smali").write_text("""
.class final Lcom/lmqr/ha9_comp_service/SettingsBackClick;
.super Ljava/lang/Object;
.implements Landroid/view/View$OnClickListener;
.field private final activity:Landroid/app/Activity;
.method public constructor <init>(Landroid/app/Activity;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/lmqr/ha9_comp_service/SettingsBackClick;->activity:Landroid/app/Activity;
    return-void
.end method
.method public onClick(Landroid/view/View;)V
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/SettingsBackClick;->activity:Landroid/app/Activity;
    invoke-virtual {v0}, Landroid/app/Activity;->finish()V
    return-void
.end method
""")
print("Patched all five modes, popup selection, broadcasts, preferences, and toolbar.")

method = """.method private final updateAodInvert(Landroid/content/SharedPreferences;)V
    .locals 3
    const-string v0, "aod_invert"
    const/4 v1, 0x1
    invoke-interface {p1, v0, v1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z
    move-result v0
    const-string v1, "aoi0"
    if-eqz v0, :off
    const-string v1, "aoi1"
    :off
    const/4 v0, 0x1
    new-array v0, v0, [Ljava/lang/String;
    const/4 v2, 0x0
    aput-object v1, v0, v2
    iget-object v1, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->commandRunner:Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;
    invoke-interface {v1, v0}, Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;->runCommands([Ljava/lang/String;)V
    return-void
.end method

"""
replace(service, ".method private final updateMaxBrightness(Landroid/content/SharedPreferences;)V",
        method + ".method private final updateMaxBrightness(Landroid/content/SharedPreferences;)V")
replace(service, '''    invoke-static {v0, v1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    .line 387''', '''    invoke-static {v0, v1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->sharedPreferences:Landroid/content/SharedPreferences;
    invoke-direct {p0, v0}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->updateAodInvert(Landroid/content/SharedPreferences;)V

    .line 387''')
replace(service, '''    .locals 2

    if-eqz p2, :cond_6''', '''    .locals 2
    const-string v0, "aod_invert"
    invoke-virtual {v0, p2}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :not_aod_invert
    invoke-direct {p0, p1}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->updateAodInvert(Landroid/content/SharedPreferences;)V
    return-void
    :not_aod_invert
    if-eqz p2, :cond_6''')
print("Patched AOD inversion preference, change handler and service startup.")

(S / "CameraLiveRefresh.smali").write_text(
    (Path(__file__).resolve().parent / "smali/CameraLiveRefresh.smali").read_text())
live = "Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->cameraLiveRefresh:Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;"
replace(service, ".field private sharedPreferences:Landroid/content/SharedPreferences;",
        ".field private cameraLiveRefresh:Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;\n\n"
        ".field private sharedPreferences:Landroid/content/SharedPreferences;")
replace(service, '''    const-wide/16 v2, 0x3e8

    invoke-virtual {v0, v1, v2, v3}, Landroid/os/Handler;->postDelayed(Ljava/lang/Runnable;J)Z

    return-void''', f'''    const-wide/16 v2, 0x3e8

    invoke-virtual {{v0, v1, v2, v3}}, Landroid/os/Handler;->postDelayed(Ljava/lang/Runnable;J)Z

    new-instance v0, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;
    invoke-direct {{v0, p0}}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;-><init>(Landroid/content/Context;)V
    iput-object v0, p0, {live}
    invoke-virtual {{v0}}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->start()V

    return-void''')
replace(service, '''    .line 380
    invoke-super {p0}, Landroid/accessibilityservice/AccessibilityService;->onDestroy()V''', f'''    iget-object v0, p0, {live}
    if-eqz v0, :no_live_refresh
    invoke-virtual {{v0}}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->stop()V
    :no_live_refresh

    .line 380
    invoke-super {{p0}}, Landroid/accessibilityservice/AccessibilityService;->onDestroy()V''')
replace(service, '''    :not_aod_invert
    if-eqz p2, :cond_6''', f'''    :not_aod_invert
    const-string v0, "camera_live_refresh"
    invoke-virtual {{v0, p2}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :not_camera_live_refresh
    iget-object v0, p0, {live}
    if-eqz v0, :camera_live_refresh_done
    invoke-virtual {{v0}}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->update()V
    :camera_live_refresh_done
    return-void
    :not_camera_live_refresh
    if-eqz p2, :cond_6''')
def camera_preference(root):
    app = "{http://schemas.android.com/apk/res-auto}"
    category = root.find("PreferenceCategory[@%stitle='EInk Service Settings']" % app)
    category.insert(0, ET.Element("SwitchPreferenceCompat", {
        app + "defaultValue": "true", app + "key": "camera_live_refresh",
        app + "summary": "Keep the camera preview updating on the E-Ink screen while a camera is open",
        app + "title": "Keep camera preview live",
    }))


xml(prefs, camera_preference)
print("Patched camera preview keep-alive.")

# Keep the legacy view IDs for the prebuilt accessor, but never show unsupported AOD controls.
replace(service, '''    const-string v9, "disable_show_per_app_aod_settings"

    invoke-interface {v6, v9, v3}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z

    move-result v6''', '''    const/4 v6, 0x1''')

manager = S / "RefreshModeManager.smali"
replace(manager, 'const-string v1, "3"', 'const-string v1, "2"')

# R8 removed unused setters in the tested APK. Restore only the APIs used by the new UI.
preference = B / "smali/androidx/preference/Preference.smali"
with preference.open("a") as output:
    for name, field, kind in (("setKey", "mKey", "Ljava/lang/String;"),
                              ("setDefaultValue", "mDefaultValue", "Ljava/lang/Object;")):
        output.write(f"""
.method public {name}({kind})V
    .locals 0
    iput-object p1, p0, Landroidx/preference/Preference;->{field}:{kind}
    return-void
.end method
""")
with (B / "smali/androidx/preference/ListPreference.smali").open("a") as output:
    for name, field in (("setEntries", "mEntries"), ("setEntryValues", "mEntryValues")):
        output.write(f"""
.method public {name}([Ljava/lang/CharSequence;)V
    .locals 0
    iput-object p1, p0, Landroidx/preference/ListPreference;->{field}:[Ljava/lang/CharSequence;
    return-void
.end method
""")
for name in ("PerAppRefreshPreference", "PerAppRefreshSettings",
             "PerAppRefreshPagePreference", "ResetAppRefreshPreference"):
    text = (Path(__file__).resolve().parent / f"smali/{name}.smali").read_text()
    for token, value in {
        "@PER_APP_XML@": hex(per_app_xml_id), "@TOOLBAR_ID@": hex(toolbar_id),
        "@REFRESH_OPTIONS@": refresh_array_ids["refresh_options"],
        "@REFRESH_VALUES@": refresh_array_ids["refresh_values"],
    }.items():
        text = text.replace(token, value)
    (S / f"{name}.smali").write_text(text)
fragment = S / "SettingsActivity$SettingsFragment.smali"
text = fragment.read_text()
start = text.index(".method public onCreatePreferences")
end = text.index("    return-void", start)
text = text[:end] + """    invoke-static {p0}, Lcom/lmqr/ha9_comp_service/PerAppRefreshSettings;->populate(Landroidx/preference/PreferenceFragmentCompat;)V

""" + text[end:]
fragment.write_text(text)
print("Patched settings order, unsupported controls, and per-app refresh selectors.")
