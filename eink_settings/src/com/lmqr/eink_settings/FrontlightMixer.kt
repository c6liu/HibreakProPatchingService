package com.lmqr.eink_settings

import kotlin.math.ln
import kotlin.math.min
import kotlin.math.pow

/**
 * Maps Android's combined brightness and a warm/cool temperature position to the two
 * LM3630A frontlight codes.
 *
 * All mixing happens in linear light. The LM3630A runs in its default exponential mapping
 * mode, where `I = I_fullscale * 0.85^(44 - (code + 1) / 5.8181818)`, so channel output is
 * converted back to codes through the inverse of that curve.
 */
object FrontlightMixer {
    const val MAX_CODE = 255

    /** Combined output never exceeds this share of both channels at full code. */
    const val OUTPUT_CAP = 0.90

    // Measured panel: cool alone 8000 K, warm alone 3000 K, both at code 255 give 4800 K.
    // That mix needs a 0.45 warm luminance share, so warm full output is 0.818 of cool.
    const val COOL_MAX_OUTPUT = 1.0
    const val WARM_MAX_OUTPUT = 0.818

    // Planckian-locus chromaticities (CIE 1931 xy) for 8000 K cool and 3000 K warm.
    private const val COOL_X = 0.2952
    private const val COOL_Y = 0.3048
    private const val WARM_X = 0.4366
    private const val WARM_Y = 0.4042

    private const val EXP_BASE = 0.85
    private const val EXP_OFFSET = 44.0
    private const val EXP_STEPS = 5.8181818

    data class Codes(val cool: Int, val warm: Int)

    /** Inverse CIE L*: equal slider steps approximate equal perceived lightness steps. */
    fun outputForLightness(position: Double): Double {
        val lightness = position.coerceIn(0.0, 1.0) * 100.0
        return if (lightness <= 8.0) lightness / (24389.0 / 27.0)
        else ((lightness + 16.0) / 116.0).pow(3.0)
    }

    fun lightnessForOutput(output: Double): Double {
        val luminance = output.coerceIn(0.0, 1.0)
        return if (luminance <= 216.0 / 24389.0) luminance * (24389.0 / 27.0) / 100.0
        else (116.0 * Math.cbrt(luminance) - 16.0) / 100.0
    }

    /** Relative output (0..1 of full scale) produced by a brightness code. */
    fun outputForCode(code: Int): Double =
        if (code <= 0) 0.0
        else EXP_BASE.pow(EXP_OFFSET - (code.coerceAtMost(MAX_CODE) + 1) / EXP_STEPS)

    /** Nearest brightness code for a relative output (0..1 of full scale). */
    fun codeForOutput(output: Double): Int {
        if (output.isNaN() || output < outputForCode(1) / 2) return 0
        if (output >= 1.0) return MAX_CODE
        val code = EXP_STEPS * (EXP_OFFSET - ln(output) / ln(EXP_BASE)) - 1
        val lower = code.toInt().coerceIn(1, MAX_CODE)
        val upper = (lower + 1).coerceAtMost(MAX_CODE)
        return if (output - outputForCode(lower) <= outputForCode(upper) - output) lower else upper
    }

    // X + 15Y + 3Z for a unit-luminance source: the weight of that source in u'v' mixing.
    private fun uvWeight(x: Double, y: Double) = (3.0 - 2.0 * x + 12.0 * y) / y

    private val COOL_UV_WEIGHT = uvWeight(COOL_X, COOL_Y)
    private val WARM_UV_WEIGHT = uvWeight(WARM_X, WARM_Y)

    /** Neutral white: both channels at full code, measured at 4800 K. */
    private val NEUTRAL_WARM_SHARE = WARM_MAX_OUTPUT / (COOL_MAX_OUTPUT + WARM_MAX_OUTPUT)

    /** Position of neutral white on the evenly spaced CIE 1976 u'v' line (about 0.415). */
    private val NEUTRAL_UV_POSITION = NEUTRAL_WARM_SHARE * WARM_UV_WEIGHT /
        (NEUTRAL_WARM_SHARE * WARM_UV_WEIGHT + (1.0 - NEUTRAL_WARM_SHARE) * COOL_UV_WEIGHT)

    /** Slider position of neutral white: the centre. */
    const val NEUTRAL_TEMPERATURE = 0.5

    // Sensitivity is constant on each side and blends smoothly across the centre ± this
    // half-width, so neither end is more than ~1.45× as sensitive as the other.
    private const val BLEND_HALF_WIDTH = 0.1

    // Slopes (relative to even u'v' spacing) are 1 ∓ CENTRE_SKEW, chosen so ease(0.5) = neutral.
    private val CENTRE_SKEW =
        (0.5 - NEUTRAL_UV_POSITION) / (0.5 - 0.375 * BLEND_HALF_WIDTH)

    // Integral of a smoothstep that rises from 0 at u = −1 to 1 at u = 1.
    private fun smoothstepIntegral(u: Double): Double = when {
        u <= -1.0 -> 0.0
        u >= 1.0 -> u
        else -> {
            val t = (u + 1.0) / 2.0
            2.0 * (t * t * t - t * t * t * t / 2.0)
        }
    }

    /** Maps a slider position to the even u'v' scale, with neutral white at 0.5. */
    internal fun ease(position: Double): Double =
        (1.0 - CENTRE_SKEW) * position + 2.0 * CENTRE_SKEW * BLEND_HALF_WIDTH *
            smoothstepIntegral((position - 0.5) / BLEND_HALF_WIDTH)

    /**
     * Warm share of combined luminance for a slider position (0 = cool, 1 = warm).
     * The slider is eased so neutral white sits at the centre, then mapped evenly along the
     * CIE 1976 u'v' line between the two LEDs. Each half has constant sensitivity (about
     * 0.82× on the cool side and 1.18× on the warm side), joined by a smooth blend.
     */
    fun warmShare(temperature: Double): Double {
        val eased = ease(temperature.coerceIn(0.0, 1.0)).coerceIn(0.0, 1.0)
        return eased * COOL_UV_WEIGHT /
            (eased * COOL_UV_WEIGHT + (1.0 - eased) * WARM_UV_WEIGHT)
    }

    /** Combined output relative to both channels at full code, for the requested inputs. */
    fun combinedOutput(brightness: Double, temperature: Double): Double {
        val target = brightness.coerceIn(0.0, 1.0) * OUTPUT_CAP * (COOL_MAX_OUTPUT + WARM_MAX_OUTPUT)
        val warm = warmShare(temperature)
        val coolLimit = if (warm < 1.0) COOL_MAX_OUTPUT / (1.0 - warm) else Double.MAX_VALUE
        val warmLimit = if (warm > 0.0) WARM_MAX_OUTPUT / warm else Double.MAX_VALUE
        // Near the endpoints one channel saturates; dim both to keep the colour unchanged.
        return min(target, min(coolLimit, warmLimit)) / (COOL_MAX_OUTPUT + WARM_MAX_OUTPUT)
    }

    /**
     * @param brightness Android's effective brightness, 0..1 in linear backlight space.
     * @param temperature 0 = fully cool, 1 = fully warm.
     */
    fun mix(brightness: Double, temperature: Double): Codes {
        val total = combinedOutput(brightness, temperature) * (COOL_MAX_OUTPUT + WARM_MAX_OUTPUT)
        val warm = warmShare(temperature)
        return Codes(
            cool = codeForOutput(total * (1.0 - warm) / COOL_MAX_OUTPUT),
            warm = codeForOutput(total * warm / WARM_MAX_OUTPUT),
        )
    }

    /** Converts a temperature seekbar position to the 0..1 temperature scale. */
    fun temperatureForProgress(progress: Int, max: Int): Double =
        if (max <= 0) 0.0 else progress.coerceIn(0, max).toDouble() / max
}
