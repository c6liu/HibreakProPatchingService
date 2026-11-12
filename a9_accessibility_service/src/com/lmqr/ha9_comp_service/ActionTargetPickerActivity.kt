package com.lmqr.ha9_comp_service

import android.content.ActivityNotFoundException
import android.content.ComponentName
import android.content.Intent
import android.graphics.drawable.Drawable
import android.os.Bundle
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.ImageView
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.widget.doAfterTextChanged
import androidx.preference.PreferenceManager
import com.google.android.material.appbar.MaterialToolbar
import com.google.android.material.snackbar.Snackbar
import com.google.android.material.tabs.TabLayout
import com.google.android.material.textfield.TextInputEditText
import java.text.Collator
import java.util.concurrent.Executors

class ActionTargetPickerActivity : AppCompatActivity() {
    private data class Target(
        val title: String,
        val detail: String,
        val icon: Drawable?,
        val select: () -> Unit,
    )

    private lateinit var actionKey: String
    private lateinit var tabs: TabLayout
    private lateinit var search: TextInputEditText
    private lateinit var notice: TextView
    private lateinit var empty: TextView
    private val adapter = TargetAdapter()
    private val loader = Executors.newSingleThreadExecutor()
    private var generation = 0
    private var apps = emptyList<Target>()
    private var shortcuts = emptyList<Target>()
    private var loaded = false
    private var loadError: String? = null

    private val configureShortcut = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            val shortcutIntent = result.data?.getParcelableExtra(
                Intent.EXTRA_SHORTCUT_INTENT, Intent::class.java
            )
            val label = result.data?.getStringExtra(Intent.EXTRA_SHORTCUT_NAME)
            if (shortcutIntent == null || label.isNullOrBlank()) {
                showError(R.string.invalid_shortcut, IllegalArgumentException("Invalid shortcut result"))
            } else {
                try {
                    ShortcutAssignment.saveLegacy(this, actionKey, label, shortcutIntent)
                    finish()
                } catch (e: IllegalArgumentException) {
                    showError(R.string.unsupported_shortcut, e)
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        theme.applyStyle(
            com.google.android.material.R.style.ThemeOverlay_Material3_DynamicColors_DayNight, true
        )
        super.onCreate(savedInstanceState)
        val requestedKey = intent.getStringExtra(EXTRA_ACTION_KEY)
        if (requestedKey !in ButtonActionSettings.actionKeys) {
            Log.e(TAG, "Invalid action key: $requestedKey")
            Toast.makeText(this, R.string.invalid_action, Toast.LENGTH_LONG).show()
            finish()
            return
        }
        actionKey = requireNotNull(requestedKey)
        setContentView(R.layout.action_target_picker)
        findViewById<MaterialToolbar>(R.id.picker_toolbar).apply {
            subtitle = gestureLabel()
            setNavigationOnClickListener { finish() }
        }
        tabs = findViewById(R.id.picker_tabs)
        search = findViewById(R.id.picker_search)
        notice = findViewById(R.id.picker_notice)
        empty = findViewById(R.id.picker_empty)
        findViewById<ListView>(R.id.picker_list).apply {
            adapter = this@ActionTargetPickerActivity.adapter
            setOnItemClickListener { _, _, position, _ -> this@ActionTargetPickerActivity.adapter.items[position].select() }
        }
        val initialTab = savedInstanceState?.getInt("tab")
            ?: if (intent.getBooleanExtra(EXTRA_SHORTCUTS, false)) 1 else 0
        tabs.getTabAt(initialTab)?.select()
        tabs.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab) = filterTargets()
            override fun onTabUnselected(tab: TabLayout.Tab) {}
            override fun onTabReselected(tab: TabLayout.Tab) {}
        })
        search.doAfterTextChanged { filterTargets() }
        filterTargets()
    }

    override fun onResume() {
        super.onResume()
        if (!::actionKey.isInitialized) return
        loadError = null
        val request = ++generation
        loader.execute {
            try {
                val appTargets = loadApps()
                val shortcutTargets = loadShortcutProviders()
                val collator = Collator.getInstance()
                val sortedApps = appTargets.sortedWith(compareBy(collator) { it.title })
                val sortedShortcuts = shortcutTargets.sortedWith(compareBy(collator) { it.title })
                runOnUiThread {
                    if (request != generation || isDestroyed || isFinishing) return@runOnUiThread
                    apps = sortedApps
                    shortcuts = sortedShortcuts
                    loaded = true
                    filterTargets()
                }
            } catch (e: SecurityException) {
                runOnUiThread {
                    if (request == generation && !isDestroyed) {
                        showError(R.string.picker_load_error, e)
                        apps = emptyList()
                        shortcuts = emptyList()
                        loadError = getString(R.string.picker_load_error)
                        filterTargets()
                    }
                }
            }
        }
    }

    private fun loadApps(): List<Target> {
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        return packageManager.queryIntentActivities(launcher, 0)
            .distinctBy { it.activityInfo.packageName }
            .map { app ->
                val packageName = app.activityInfo.packageName
                Target(app.loadLabel(packageManager).toString(), packageName, app.loadIcon(packageManager)) {
                    PreferenceManager.getDefaultSharedPreferences(this).edit()
                        .putString("launch_app_package_$actionKey", packageName)
                        .putString(actionKey, "launch_app_$actionKey")
                        .apply()
                    finish()
                }
            }
    }

    @Suppress("DEPRECATION")
    private fun loadShortcutProviders(): List<Target> =
        packageManager.queryIntentActivities(Intent(Intent.ACTION_CREATE_SHORTCUT), 0)
            .filter { it.activityInfo.exported && it.activityInfo.enabled }
            .map { provider ->
                val component = ComponentName(provider.activityInfo.packageName, provider.activityInfo.name)
                Target(
                    provider.loadLabel(packageManager).toString(),
                    getString(R.string.configure_shortcut_detail, component.packageName),
                    provider.loadIcon(packageManager),
                ) {
                    try {
                        configureShortcut.launch(Intent(Intent.ACTION_CREATE_SHORTCUT).setComponent(component))
                    } catch (e: ActivityNotFoundException) {
                        showError(R.string.unavailable_shortcut, e)
                    } catch (e: SecurityException) {
                        showError(R.string.blocked_target, e)
                    }
                }
            }

    private fun filterTargets() {
        val isShortcuts = tabs.selectedTabPosition == 1
        val query = search.text?.toString().orEmpty().trim()
        adapter.items = (if (isShortcuts) shortcuts else apps).filter {
            it.title.contains(query, ignoreCase = true) || it.detail.contains(query, ignoreCase = true)
        }
        adapter.notifyDataSetChanged()
        notice.visibility = if (isShortcuts) View.VISIBLE else View.GONE
        notice.setText(R.string.shortcut_picker_help)
        empty.visibility = if (adapter.items.isEmpty()) View.VISIBLE else View.GONE
        empty.text = loadError ?: getString(when {
            !loaded -> R.string.loading_targets
            query.isNotEmpty() -> R.string.no_matching_targets
            isShortcuts -> R.string.no_shortcuts
            else -> R.string.no_apps
        })
    }

    private fun gestureLabel(): String {
        val button = getString(if (actionKey.startsWith("top_")) R.string.top_button else R.string.bottom_button)
        val gesture = getString(when {
            actionKey.contains("double_press") -> R.string.double_press
            actionKey.contains("long_press") -> R.string.long_press
            else -> R.string.single_press
        })
        val screen = getString(if (actionKey.endsWith("_screen_off")) R.string.screen_off else R.string.screen_on)
        return getString(R.string.gesture_description, button, gesture, screen)
    }

    private fun showError(message: Int, error: Exception) {
        Log.e(TAG, getString(message), error)
        Snackbar.make(findViewById(R.id.picker_list), message, Snackbar.LENGTH_LONG).show()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        if (::tabs.isInitialized) outState.putInt("tab", tabs.selectedTabPosition)
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        generation++
        loader.shutdownNow()
        super.onDestroy()
    }

    private inner class TargetAdapter : BaseAdapter() {
        var items = emptyList<Target>()
        override fun getCount() = items.size
        override fun getItem(position: Int) = items[position]
        override fun getItemId(position: Int) = position.toLong()
        override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
            val row = convertView ?: layoutInflater.inflate(R.layout.action_target_row, parent, false)
            val target = getItem(position)
            row.findViewById<TextView>(R.id.target_title).text = target.title
            row.findViewById<TextView>(R.id.target_detail).text = target.detail
            row.findViewById<ImageView>(R.id.target_icon).setImageDrawable(target.icon)
            return row
        }
    }

    companion object {
        const val EXTRA_ACTION_KEY = "action_key"
        const val EXTRA_SHORTCUTS = "shortcuts"
        private const val TAG = "A9ActionTargetPicker"
    }
}
