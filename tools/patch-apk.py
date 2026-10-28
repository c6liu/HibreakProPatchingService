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
video_refresh_id = add_public(public.getroot(), "id", "video_optimized_refresh")
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

manifest_path = B / "AndroidManifest.xml"
manifest_tree = ET.parse(manifest_path)
manifest_root = manifest_tree.getroot()
for permission_name in ("android.permission.WAKE_LOCK", "android.permission.TURN_SCREEN_ON"):
    if manifest_root.find(f"uses-permission[@{A}name='{permission_name}']") is None:
        manifest_root.insert(0, ET.Element("uses-permission", {A + "name": permission_name}))
queries = manifest_root.find("queries")
if queries is None:
    queries = ET.Element("queries")
    application = manifest_root.find("application")
    manifest_root.insert(list(manifest_root).index(application), queries)
launcher_action = f"action[@{A}name='android.intent.action.MAIN']"
launcher_category = f"category[@{A}name='android.intent.category.LAUNCHER']"
launcher_query = next((query for query in queries.findall("intent")
                       if query.find(launcher_action) is not None
                       and query.find(launcher_category) is not None), None)
if launcher_query is None:
    launcher_query = ET.SubElement(queries, "intent")
if launcher_query.find(launcher_action) is None:
    ET.SubElement(launcher_query, "action", {A + "name": "android.intent.action.MAIN"})
if launcher_query.find(launcher_category) is None:
    ET.SubElement(launcher_query, "category", {A + "name": "android.intent.category.LAUNCHER"})
manifest_tree.write(manifest_path, encoding="utf-8", xml_declaration=True)


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


def button_actions(root):
    options = root.find("string-array[@name='button_action_entries']")
    values = root.find("string-array[@name='button_action_values']")
    labels = [item.text for item in options.findall("item")]
    keys = [item.text for item in values.findall("item")]
    assert len(labels) == len(keys)
    actions = list(zip(labels, keys))
    assert ("Toggle Night Light", "toggle_night_light") in actions
    assert ("Toggle Backlight", "toggle_backlight") in actions
    actions = [action for action in actions
               if action not in (("Toggle Night Light", "toggle_night_light"),
                                 ("Toggle Backlight", "toggle_backlight"))]
    clear_index = actions.index(("Clear Screen", "clear")) + 1
    actions[clear_index:clear_index] = [
        ("Up", "dpad_up"), ("Down", "dpad_down"),
        ("Left", "dpad_left"), ("Right", "dpad_right"),
    ]
    options.clear()
    options.set("name", "button_action_entries")
    values.clear()
    values.set("name", "button_action_values")
    for label, key in actions:
        ET.SubElement(options, "item").text = label
        ET.SubElement(values, "item").text = key


xml(B / "res/values/arrays.xml", button_actions)


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
    anti_shake = root.find(f".//*[@{A}id='@id/anti_shake']")
    assert anti_shake is not None
    row = next(node for node in root.iter() if anti_shake in list(node))
    controls = next(node for node in root.iter() if row in list(node))
    source = ET.parse(REPO / "res/layout/floating_menu_layout.xml").getroot()
    toggle = source.find(f".//*[@{A}id='@+id/video_optimized_refresh']")
    assert toggle is not None
    toggle.set(A + "id", "@id/video_optimized_refresh")
    controls.insert(list(controls).index(row) + 1, toggle)


xml(B / "res/layout/floating_menu_layout.xml", menu)
(B / "res/layout/settings_activity.xml").write_text(
    (REPO / "res/layout/settings_activity.xml").read_text())


def styles(root):
    style = ET.SubElement(root, "style", name="Theme.Ha9_comp_service.Settings",
                          parent="@style/Theme.Material3.DayNight.NoActionBar")
    ET.SubElement(style, "item", name="windowActionBar").text = "false"
    ET.SubElement(style, "item", name="windowNoTitle").text = "true"
    ET.SubElement(style, "item", name="android:windowLightStatusBar").text = "?attr/isLightTheme"
    for name, value in (
            ("colorPrimary", "#FF000000"),
            ("colorOnPrimary", "#FFFFFFFF"),
            ("colorSecondary", "#FF000000"),
            ("colorOnSecondary", "#FFFFFFFF"),
            ("colorSurface", "#FFFFFFFF"),
            ("colorOnSurface", "#FF000000"),
            ("colorSurfaceVariant", "#FFF2F2F2"),
            ("colorOnSurfaceVariant", "#FF222222"),
            ("colorOutline", "#FF5F5F5F"),
            ("android:colorAccent", "#FF000000"),
            ("colorControlActivated", "#FF000000"),
            ("android:statusBarColor", "#FFFFFFFF"),
            ("android:navigationBarColor", "#FFFFFFFF"),
            ("android:windowLightNavigationBar", "true")):
        ET.SubElement(style, "item", name=name).text = value


xml(B / "res/values/styles.xml", styles)

def night_styles(root):
    style = ET.SubElement(root, "style", name="Theme.Ha9_comp_service.Settings",
                          parent="@style/Theme.Material3.DayNight.NoActionBar")
    for name, value in (
            ("windowActionBar", "false"),
            ("windowNoTitle", "true"),
            ("android:windowLightStatusBar", "false"),
            ("colorPrimary", "#FFFFFFFF"),
            ("colorOnPrimary", "#FF000000"),
            ("colorSecondary", "#FFFFFFFF"),
            ("colorOnSecondary", "#FF000000"),
            ("colorSurface", "#FF000000"),
            ("colorOnSurface", "#FFFFFFFF"),
            ("colorSurfaceVariant", "#FF202020"),
            ("colorOnSurfaceVariant", "#FFE0E0E0"),
            ("colorOutline", "#FFBDBDBD"),
            ("android:colorAccent", "#FFFFFFFF"),
            ("colorControlActivated", "#FFFFFFFF"),
            ("android:statusBarColor", "#FF000000"),
            ("android:navigationBarColor", "#FF000000"),
            ("android:windowLightNavigationBar", "false")):
        ET.SubElement(style, "item", name=name).text = value


xml(B / "res/values-night/styles.xml", night_styles)


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
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->displaySettingsManager:Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;
    invoke-virtual {{v0}}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->applySettings()V

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
replace(manager, 'const-string v1, "3"', 'const-string v1, "1"')

# R8 removed unused setters in the tested APK. Restore only the APIs used by the new UI.
preference = B / "smali/androidx/preference/Preference.smali"
replace(preference, '.super Ljava/lang/Object;',
        '.super Ljava/lang/Object;\n\n'
        '.field private mOnChangeListener:Landroidx/preference/Preference$OnPreferenceChangeListener;')
replace(preference, """.method public callChangeListener(Ljava/lang/Object;)Z
    .locals 0

    .line 0
    const/4 p0, 0x1

    return p0
.end method""", """.method public callChangeListener(Ljava/lang/Object;)Z
    .locals 1
    iget-object v0, p0, Landroidx/preference/Preference;->mOnChangeListener:Landroidx/preference/Preference$OnPreferenceChangeListener;
    if-eqz v0, :accept
    invoke-interface {v0, p0, p1}, Landroidx/preference/Preference$OnPreferenceChangeListener;->onPreferenceChange(Landroidx/preference/Preference;Ljava/lang/Object;)Z
    move-result v0
    return v0
    :accept
    const/4 v0, 0x1
    return v0
.end method""")
(preference.parent / "Preference$OnPreferenceChangeListener.smali").write_text(
    (Path(__file__).resolve().parent / "smali/PreferenceChangeListener.smali").read_text())
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
    invoke-static {p0}, Lcom/lmqr/ha9_comp_service/AppLaunchSettings;->populate(Landroidx/preference/PreferenceFragmentCompat;)V

""" + text[end:]
fragment.write_text(text)
(S / "AppLaunchSettings.smali").write_text(
    (Path(__file__).resolve().parent / "smali/AppLaunchSettings.smali").read_text())
(S / "AppLaunchPreferenceBinding.smali").write_text(
    (Path(__file__).resolve().parent / "smali/AppLaunchPreferenceBinding.smali").read_text())
launch_action = (Path(__file__).resolve().parent / "smali/LaunchAppButtonAction.smali")
(S / "button_mapper/LaunchAppButtonAction.smali").write_text(launch_action.read_text())
launch_action_map = (Path(__file__).resolve().parent / "smali/AppLaunchActionMap.smali")
(S / "button_mapper/AppLaunchActionMap.smali").write_text(launch_action_map.read_text())
# Restore setters removed by R8 that the new app pickers need.
dialog_preference = B / "smali/androidx/preference/DialogPreference.smali"
with dialog_preference.open("a") as output:
    output.write("""
.method public setDialogTitle(Ljava/lang/CharSequence;)V
    .locals 0
    iput-object p1, p0, Landroidx/preference/DialogPreference;->mDialogTitle:Ljava/lang/CharSequence;
    return-void
.end method
""")
preference = B / "smali/androidx/preference/Preference.smali"
with preference.open("a") as output:
    output.write("""
.method public setOnPreferenceChangeListener(Landroidx/preference/Preference$OnPreferenceChangeListener;)V
    .locals 0
    iput-object p1, p0, Landroidx/preference/Preference;->mOnChangeListener:Landroidx/preference/Preference$OnPreferenceChangeListener;
    return-void
.end method

.method public final setVisible(Z)V
    .locals 1
    iget-boolean v0, p0, Landroidx/preference/Preference;->mVisible:Z
    if-eq v0, p1, :visible_done
    iput-boolean p1, p0, Landroidx/preference/Preference;->mVisible:Z
    invoke-virtual {p0}, Landroidx/preference/Preference;->notifyHierarchyChanged()V
    :visible_done
    return-void
.end method

.method public setEnabled(Z)V
    .locals 1
    iget-boolean v0, p0, Landroidx/preference/Preference;->mEnabled:Z
    if-eq v0, p1, :done
    iput-boolean p1, p0, Landroidx/preference/Preference;->mEnabled:Z
    invoke-virtual {p0}, Landroidx/preference/Preference;->shouldDisableDependents()Z
    move-result v0
    invoke-virtual {p0, v0}, Landroidx/preference/Preference;->notifyDependencyChange(Z)V
    invoke-virtual {p0}, Landroidx/preference/Preference;->notifyChanged()V
    :done
    return-void
.end method
""")
print("Patched side-key app launching, settings, and display controls.")

accessor = S / "FloatingMenuViewAccessor.smali"
replace(accessor, ".field private final autoRefresh:Landroid/widget/Switch;",
        ".field private final autoRefresh:Landroid/widget/Switch;\n\n"
        ".field private final videoOptimizedRefresh:Landroid/widget/Switch;")
replace(accessor, '''    iput-object v0, p0, Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;->antiShake:Landroid/widget/Switch;
''', f'''    iput-object v0, p0, Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;->antiShake:Landroid/widget/Switch;

    const v0, {hex(video_refresh_id)}
    invoke-virtual {{p1, v0}}, Landroid/view/View;->findViewById(I)Landroid/view/View;
    move-result-object v0
    check-cast v0, Landroid/widget/Switch;
    iput-object v0, p0, Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;->videoOptimizedRefresh:Landroid/widget/Switch;
''')
with accessor.open("a") as output:
    output.write("""
.method public final getVideoOptimizedRefresh()Landroid/widget/Switch;
    .locals 0
    iget-object p0, p0, Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;->videoOptimizedRefresh:Landroid/widget/Switch;
    return-object p0
.end method
""")

action_manager = S / "button_mapper/ButtonActionManager.smali"
replace(action_manager, "    .locals 11", "    .locals 13")
# The upstream constructor reuses p1 for action objects after creating Clear Screen.
replace(action_manager, '''    const-string v0, "commandRunner"''', '''    move-object v12, p1

    const-string v0, "commandRunner"''')
replace(action_manager, '''    .line 17
    new-instance p1, Lcom/lmqr/ha9_comp_service/button_mapper/ToggleNightLightAction;

    invoke-direct {p1}, Lcom/lmqr/ha9_comp_service/button_mapper/ToggleNightLightAction;-><init>()V

    const-string p2, "toggle_night_light"

    invoke-static {p2, p1}, Lkotlin/TuplesKt;->to(Ljava/lang/Object;Ljava/lang/Object;)Lkotlin/Pair;

    move-result-object v8

    .line 18
    new-instance p1, Lcom/lmqr/ha9_comp_service/button_mapper/ToggleBacklightAction;

    invoke-direct {p1}, Lcom/lmqr/ha9_comp_service/button_mapper/ToggleBacklightAction;-><init>()V

    const-string p2, "toggle_backlight"

    invoke-static {p2, p1}, Lkotlin/TuplesKt;->to(Ljava/lang/Object;Ljava/lang/Object;)Lkotlin/Pair;

    move-result-object v9

    .line 19
    new-instance p1, Lcom/lmqr/ha9_comp_service/button_mapper/PreviousTrackButtonAction;

    invoke-direct {p1}, Lcom/lmqr/ha9_comp_service/button_mapper/PreviousTrackButtonAction;-><init>()V

    const-string p2, "previous_track"

    invoke-static {p2, p1}, Lkotlin/TuplesKt;->to(Ljava/lang/Object;Ljava/lang/Object;)Lkotlin/Pair;

    move-result-object v10

    filled-new-array/range {v1 .. v10}, [Lkotlin/Pair;''', '''    .line 17
    new-instance v0, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;

    const-string p2, "dpad_up"

    invoke-direct {v0, v12, p2}, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;-><init>(Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;Ljava/lang/String;)V

    invoke-static {p2, v0}, Lkotlin/TuplesKt;->to(Ljava/lang/Object;Ljava/lang/Object;)Lkotlin/Pair;

    move-result-object v8

    new-instance v0, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;
    const-string p2, "dpad_down"
    invoke-direct {v0, v12, p2}, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;-><init>(Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;Ljava/lang/String;)V
    invoke-static {p2, v0}, Lkotlin/TuplesKt;->to(Ljava/lang/Object;Ljava/lang/Object;)Lkotlin/Pair;
    move-result-object v9

    new-instance v0, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;
    const-string p2, "dpad_left"
    invoke-direct {v0, v12, p2}, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;-><init>(Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;Ljava/lang/String;)V
    invoke-static {p2, v0}, Lkotlin/TuplesKt;->to(Ljava/lang/Object;Ljava/lang/Object;)Lkotlin/Pair;
    move-result-object v10

    new-instance v0, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;
    const-string p2, "dpad_right"
    invoke-direct {v0, v12, p2}, Lcom/lmqr/ha9_comp_service/button_mapper/DpadButtonAction;-><init>(Lcom/lmqr/ha9_comp_service/command_runners/CommandRunner;Ljava/lang/String;)V
    invoke-static {p2, v0}, Lkotlin/TuplesKt;->to(Ljava/lang/Object;Ljava/lang/Object;)Lkotlin/Pair;
    move-result-object v11

    new-instance p1, Lcom/lmqr/ha9_comp_service/button_mapper/PreviousTrackButtonAction;
    invoke-direct {p1}, Lcom/lmqr/ha9_comp_service/button_mapper/PreviousTrackButtonAction;-><init>()V
    const-string p2, "previous_track"
    invoke-static {p2, p1}, Lkotlin/TuplesKt;->to(Ljava/lang/Object;Ljava/lang/Object;)Lkotlin/Pair;
    move-result-object v12

    filled-new-array/range {v1 .. v12}, [Lkotlin/Pair;''')
replace(action_manager, '''    .line 20
    sget-object p2, Lcom/lmqr/ha9_comp_service/button_mapper/ButtonActionManager$buttonCommands$1;->INSTANCE:Lcom/lmqr/ha9_comp_service/button_mapper/ButtonActionManager$buttonCommands$1;
''', '''    invoke-static {p1}, Lcom/lmqr/ha9_comp_service/button_mapper/AppLaunchActionMap;->addToMap(Ljava/util/Map;)Ljava/util/Map;
    move-result-object p1

    .line 20
    sget-object p2, Lcom/lmqr/ha9_comp_service/button_mapper/ButtonActionManager$buttonCommands$1;->INSTANCE:Lcom/lmqr/ha9_comp_service/button_mapper/ButtonActionManager$buttonCommands$1;
''')
(S / "button_mapper/DpadButtonAction.smali").write_text(
    (Path(__file__).resolve().parent / "smali/DpadButtonAction.smali").read_text())
for obsolete in (
        B / "smali/SystemSettingsManager.smali",
        S / "button_mapper/ToggleNightLightAction.smali",
        S / "button_mapper/ToggleBacklightAction.smali"):
    obsolete.unlink()

service = S / "A9AccessibilityService.smali"
(S / "ScreenOffKeyReceiver.smali").write_text(
    (Path(__file__).resolve().parent / "smali/ScreenOffKeyReceiver.smali").read_text())
replace(service, ".field private isScreenOn:Z",
        ".field private isScreenOn:Z\n"
        ".field private screenOffKeyReceiver:Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;")
replace(service, '''    invoke-virtual {p0, v1, v0, v2}, Landroid/accessibilityservice/AccessibilityService;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;I)Landroid/content/Intent;

    return-void''', '''    invoke-virtual {p0, v1, v0, v2}, Landroid/accessibilityservice/AccessibilityService;->registerReceiver(Landroid/content/BroadcastReceiver;Landroid/content/IntentFilter;I)Landroid/content/Intent;
    new-instance v0, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;
    invoke-direct {v0, p0}, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;-><init>(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)V
    iput-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->screenOffKeyReceiver:Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;
    return-void''')
replace(service, '''    invoke-super {p0}, Landroid/accessibilityservice/AccessibilityService;->onDestroy()V''',
        '''    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->screenOffKeyReceiver:Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;
    invoke-virtual {v0}, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->close()V
    invoke-super {p0}, Landroid/accessibilityservice/AccessibilityService;->onDestroy()V''')
for suffix, scan_code in (("", "0x3b"), ("Top", "0x3c")):
    listener = S / f"A9AccessibilityService$hardwareGestureDetector{suffix}$1.smali"
    replace(listener,
            "    invoke-static {v0}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;"
            "->access$isScreenOn$p(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)Z",
            f"    const/16 v1, {scan_code}\n"
            "    invoke-virtual {v0, v1}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;"
            "->isSideKeyScreenOn(I)Z", count=3)
replace(service, '''    invoke-virtual {v6, v9, v10}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->setupSwitches(Landroid/widget/CompoundButton;Landroid/widget/CompoundButton;)V''', '''    invoke-virtual {v6, v9, v10}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->setupSwitches(Landroid/widget/CompoundButton;Landroid/widget/CompoundButton;)V
    invoke-virtual {v8}, Lcom/lmqr/ha9_comp_service/FloatingMenuViewAccessor;->getVideoOptimizedRefresh()Landroid/widget/Switch;
    move-result-object v9
    invoke-static {p0, v9}, Lcom/lmqr/ha9_comp_service/VideoRefreshSwitchSetup;->setup(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;Landroid/widget/Switch;)V''')
key_method = re.search(
    r"\.method protected onKeyEvent\(Landroid/view/KeyEvent;\)Z.*?\.end method",
    service.read_text(), re.S)
assert key_method is not None
replace(service, key_method.group(), '''.method protected onKeyEvent(Landroid/view/KeyEvent;)Z
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->screenOffKeyReceiver:Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;
    invoke-virtual {v0, p1}, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->onKeyEvent(Landroid/view/KeyEvent;)Z
    move-result v0
    if-eqz v0, :forward_other_key
    return v0
    :forward_other_key
    invoke-super {p0, p1}, Landroid/accessibilityservice/AccessibilityService;->onKeyEvent(Landroid/view/KeyEvent;)Z
    move-result v0
    return v0
.end method''')
with service.open("a") as output:
    output.write("""
.method public final dispatchSideKey(IIJ)V
    .locals 2
    invoke-virtual {p0}, Landroid/content/ContextWrapper;->getBaseContext()Landroid/content/Context;
    move-result-object v0
    invoke-static {v0}, Landroid/provider/Settings;->canDrawOverlays(Landroid/content/Context;)Z
    move-result v0
    if-nez v0, :dispatch
    invoke-direct {p0}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->requestOverlayPermission()V
    return-void
    :dispatch
    const/16 v0, 0x3b
    if-ne p1, v0, :top
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->hardwareGestureDetector:Lcom/lmqr/ha9_comp_service/HardwareGestureDetector;
    goto :send
    :top
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->hardwareGestureDetectorTop:Lcom/lmqr/ha9_comp_service/HardwareGestureDetector;
    :send
    invoke-virtual {v0, p2, p3, p4}, Lcom/lmqr/ha9_comp_service/HardwareGestureDetector;->onKeyEvent(IJ)V
    return-void
.end method

.method public final isSideKeyScreenOn(I)Z
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->screenOffKeyReceiver:Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;
    invoke-virtual {v0, p1}, Lcom/lmqr/ha9_comp_service/ScreenOffKeyReceiver;->isScreenOn(I)Z
    move-result v0
    return v0
.end method

.method public final setVideoOptimizedRefresh(Z)V
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->cameraLiveRefresh:Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;
    if-eqz v0, :video_refresh_done
    invoke-virtual {v0, p1}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->setVideoOptimized(Z)V
    :video_refresh_done
    return-void
.end method

.method public final setupVideoRefreshSwitch(Landroid/widget/CompoundButton;)V
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->displaySettingsManager:Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;
    invoke-virtual {v0, p1}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->setupVideo(Landroid/widget/CompoundButton;)V
    return-void
.end method

.method public final onDisplayAppChange(Ljava/lang/String;)V
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->displaySettingsManager:Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;
    invoke-virtual {v0, p1}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->onAppChange(Ljava/lang/String;)V
    return-void
.end method

.method public final setLiveRefreshScreenOn(Z)V
    .locals 1
    iget-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->cameraLiveRefresh:Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;
    if-eqz v0, :screen_refresh_done
    invoke-virtual {v0, p1}, Lcom/lmqr/ha9_comp_service/CameraLiveRefresh;->setScreenOn(Z)V
    :screen_refresh_done
    return-void
.end method
""")

receiver = S / "A9AccessibilityService$receiver$1.smali"
replace(receiver, '''    invoke-static {p1, p2}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->access$setScreenOn$p(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;Z)V''', '''    invoke-static {p1, p2}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->access$setScreenOn$p(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;Z)V
    invoke-virtual {p1, p2}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->setLiveRefreshScreenOn(Z)V''')
replace(receiver, '''    invoke-static {p1, v4}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->access$setScreenOn$p(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;Z)V''', '''    invoke-static {p1, v4}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->access$setScreenOn$p(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;Z)V
    invoke-virtual {p1, v4}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->setLiveRefreshScreenOn(Z)V''')

replace(service, '''    iput-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->displaySettingsManager:Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;''', '''    iput-object v0, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->displaySettingsManager:Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;
    invoke-virtual {v0, p0}, Lcom/lmqr/ha9_comp_service/DisplaySettingsManager;->attach(Lcom/lmqr/ha9_comp_service/A9AccessibilityService;)V''')
app_event = S / "A9AccessibilityService$onAccessibilityEvent$1.smali"
replace(app_event, '''    invoke-virtual {p2, p1}, Lcom/lmqr/ha9_comp_service/RefreshModeManager;->onAppChange(Ljava/lang/String;)V''', '''    invoke-virtual {p2, p1}, Lcom/lmqr/ha9_comp_service/RefreshModeManager;->onAppChange(Ljava/lang/String;)V
    iget-object p2, p0, Lcom/lmqr/ha9_comp_service/A9AccessibilityService$onAccessibilityEvent$1;->this$0:Lcom/lmqr/ha9_comp_service/A9AccessibilityService;
    invoke-virtual {p2, p1}, Lcom/lmqr/ha9_comp_service/A9AccessibilityService;->onDisplayAppChange(Ljava/lang/String;)V''')

for name in ("CameraLiveRefresh", "VideoRefreshSwitchSetup", "DisplaySettingsManager"):
    (S / f"{name}.smali").write_text(
        (Path(__file__).resolve().parent / f"smali/{name}.smali").read_text())
