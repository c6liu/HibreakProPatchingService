package com.lmqr.eink_settings

import android.content.Context
import android.os.Environment
import java.io.File

fun getBackgroundFileImage(ctx: Context): File {
    if(Environment.isExternalStorageManager()) {
        val dir = File(Environment.getExternalStoragePublicDirectory("/"), "eink_settings")
        if (!dir.exists())
            dir.mkdirs()

        return File(dir, "bgimage")
    }
    return File(ctx.filesDir, "bgimage")
}