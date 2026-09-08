package za.co.dioworkflows.mobile.security

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyFactory
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.spec.PKCS8EncodedKeySpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import net.schmizz.sshj.common.Buffer

/**
 * Owns DIO Mobile's app-specific SSH identity.
 *
 * The SSH key pair is generated inside the app. Exportable PKCS#8 private-key bytes are
 * encrypted with an AES-256-GCM wrapping key held by AndroidKeyStore before persistence.
 * Only public material and AES ciphertext/IV are stored in SharedPreferences.
 */
class SecureIdentityStore(context: Context) {
    data class PublicIdentity(
        val openSshPublicKey: String,
        val fingerprint: String,
    )

    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun createIdentity(): PublicIdentity {
        publicIdentityOrNull()?.let { existing ->
            require(prefs.contains(PREF_CIPHERTEXT) && prefs.contains(PREF_IV)) {
                "DIO Mobile SSH identity is incomplete"
            }
            return existing
        }

        val generator = KeyPairGenerator.getInstance(KEY_ALGORITHM)
        generator.initialize(KEY_SIZE_BITS, SecureRandom())
        val pair = generator.generateKeyPair()
        val secretBytes = pair.private.encoded
            ?: throw IllegalStateException("SSH private key is not exportable")

        try {
            val cipher = Cipher.getInstance(CIPHER_TRANSFORMATION)
            cipher.init(Cipher.ENCRYPT_MODE, getOrCreateWrapKey())
            val ciphertext = cipher.doFinal(secretBytes)
            val publicBytes = pair.public.encoded
            val publicBlob = Buffer.PlainBuffer().putPublicKey(pair.public).compactData
            val openSshPublicKey =
                "ssh-rsa ${Base64.getEncoder().encodeToString(publicBlob)} dio-mobile"
            val fingerprint = sha256Fingerprint(publicBlob)

            prefs.edit()
                .putString(PREF_CIPHERTEXT, Base64.getEncoder().encodeToString(ciphertext))
                .putString(PREF_IV, Base64.getEncoder().encodeToString(cipher.iv))
                .putString(PREF_PUBLIC_X509, Base64.getEncoder().encodeToString(publicBytes))
                .putString(PREF_OPENSSH_PUBLIC, openSshPublicKey)
                .putString(PREF_PUBLIC_FINGERPRINT, fingerprint)
                .apply()

            return PublicIdentity(openSshPublicKey, fingerprint)
        } finally {
            secretBytes.fill(0)
        }
    }

    fun publicIdentity(): PublicIdentity =
        publicIdentityOrNull() ?: throw IllegalStateException("DIO Mobile SSH identity is not configured")

    fun loadPrivateKeyBytes(): ByteArray {
        val ciphertext = requirePreference(PREF_CIPHERTEXT)
        val iv = requirePreference(PREF_IV)
        val cipher = Cipher.getInstance(CIPHER_TRANSFORMATION)
        cipher.init(
            Cipher.DECRYPT_MODE,
            getExistingWrapKey(),
            GCMParameterSpec(GCM_TAG_BITS, Base64.getDecoder().decode(iv)),
        )
        return cipher.doFinal(Base64.getDecoder().decode(ciphertext))
    }

    fun loadKeyPair(): KeyPair {
        val secretBytes = loadPrivateKeyBytes()
        return try {
            val factory = KeyFactory.getInstance(KEY_ALGORITHM)
            val privateKey = factory.generatePrivate(PKCS8EncodedKeySpec(secretBytes))
            val publicBytes = Base64.getDecoder().decode(requirePreference(PREF_PUBLIC_X509))
            val publicKey = factory.generatePublic(X509EncodedKeySpec(publicBytes))
            KeyPair(publicKey, privateKey)
        } finally {
            secretBytes.fill(0)
        }
    }

    fun clearIdentity() {
        prefs.edit().clear().apply()
        val keyStore = androidKeyStore()
        if (keyStore.containsAlias(WRAP_KEY_ALIAS)) {
            keyStore.deleteEntry(WRAP_KEY_ALIAS)
        }
    }

    private fun publicIdentityOrNull(): PublicIdentity? {
        val openSsh = prefs.getString(PREF_OPENSSH_PUBLIC, null) ?: return null
        val fingerprint = prefs.getString(PREF_PUBLIC_FINGERPRINT, null) ?: return null
        return PublicIdentity(openSsh, fingerprint)
    }

    private fun requirePreference(key: String): String =
        prefs.getString(key, null) ?: throw IllegalStateException("DIO Mobile SSH identity is incomplete")

    private fun getOrCreateWrapKey(): SecretKey {
        val keyStore = androidKeyStore()
        (keyStore.getKey(WRAP_KEY_ALIAS, null) as? SecretKey)?.let { return it }

        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEY_STORE)
        val spec = KeyGenParameterSpec.Builder(
            WRAP_KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build()
        generator.init(spec)
        return generator.generateKey()
    }

    private fun getExistingWrapKey(): SecretKey =
        androidKeyStore().getKey(WRAP_KEY_ALIAS, null) as? SecretKey
            ?: throw IllegalStateException("AndroidKeyStore wrapping key is missing")

    private fun androidKeyStore(): KeyStore =
        KeyStore.getInstance(ANDROID_KEY_STORE).apply { load(null) }

    private fun sha256Fingerprint(publicBlob: ByteArray): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(publicBlob)
        return "SHA256:${Base64.getEncoder().withoutPadding().encodeToString(digest)}"
    }

    companion object {
        private const val ANDROID_KEY_STORE = "AndroidKeyStore"
        private const val CIPHER_TRANSFORMATION = "AES/GCM/NoPadding"
        private const val GCM_TAG_BITS = 128
        private const val KEY_ALGORITHM = "RSA"
        private const val KEY_SIZE_BITS = 3072
        private const val WRAP_KEY_ALIAS = "dio.mobile.identity.wrap.v1"
        private const val PREFS_NAME = "dio_mobile_identity_v1"
        private const val PREF_CIPHERTEXT = "ciphertext_v1"
        private const val PREF_IV = "iv_v1"
        private const val PREF_PUBLIC_X509 = "public_x509_v1"
        private const val PREF_OPENSSH_PUBLIC = "openssh_public_v1"
        private const val PREF_PUBLIC_FINGERPRINT = "public_fingerprint_v1"
    }
}
