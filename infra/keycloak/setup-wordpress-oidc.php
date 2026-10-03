<?php
/** Run inside the WordPress container with the client secret on standard input. */

require '/var/www/html/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
require_once ABSPATH . 'wp-admin/includes/plugin-install.php';
require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';

$secret = trim(stream_get_contents(STDIN));
if (strlen($secret) < 32) {
    fwrite(STDERR, "Missing OIDC client secret\n");
    exit(1);
}
if (parse_url(site_url(), PHP_URL_HOST) !== 'alkemata.com') {
    fwrite(STDERR, 'Unexpected WordPress site URL: ' . site_url() . "\n");
    exit(1);
}
$admin = get_user_by('login', 'rdi33');
if (!$admin || strtolower($admin->user_email) !== 'info@alkemata.com' || !in_array('administrator', $admin->roles, true)) {
    fwrite(STDERR, "Matching WordPress administrator rdi33 not found\n");
    exit(1);
}

$plugin = 'daggerhart-openid-connect-generic/openid-connect-generic.php';
if (!file_exists(WP_PLUGIN_DIR . '/' . $plugin)) {
    $info = plugins_api('plugin_information', array(
        'slug' => 'daggerhart-openid-connect-generic',
        'fields' => array('sections' => false),
    ));
    if (is_wp_error($info) || empty($info->download_link)) {
        fwrite(STDERR, "Could not locate the OIDC plugin on WordPress.org\n");
        exit(1);
    }
    $upgrader = new Plugin_Upgrader(new Automatic_Upgrader_Skin());
    $result = $upgrader->install($info->download_link);
    if ($result !== true || !file_exists(WP_PLUGIN_DIR . '/' . $plugin)) {
        $error = is_wp_error($result) ? $result->get_error_message() : var_export($result, true);
        $skin_errors = $upgrader->skin->get_errors();
        if (is_wp_error($skin_errors) && $skin_errors->has_errors()) {
            $error .= '; ' . implode('; ', $skin_errors->get_error_messages());
        }
        fwrite(STDERR, "OIDC plugin installation failed: " . $error . "\n");
        exit(1);
    }
}

$existing = get_option('openid_connect_generic_settings', array());
if (!empty($existing['client_id']) && $existing['client_id'] !== 'wordpress') {
    fwrite(STDERR, "An OIDC client is already configured; no settings changed\n");
    exit(1);
}
$base = 'https://auth.alkemata.com/realms/alkemata';
$settings = array_merge((array) $existing, array(
    'login_type' => 'button',
    'login_button_text' => 'Sign in with Alkemata',
    'client_id' => 'wordpress',
    'client_secret' => $secret,
    'scope' => 'openid profile email',
    'endpoint_login' => $base . '/protocol/openid-connect/auth',
    'endpoint_userinfo' => $base . '/protocol/openid-connect/userinfo',
    'endpoint_token' => $base . '/protocol/openid-connect/token',
    'endpoint_end_session' => $base . '/protocol/openid-connect/logout',
    'endpoint_jwks' => $base . '/protocol/openid-connect/certs',
    'issuer' => $base,
    'identity_key' => 'sub',
    'nickname_key' => 'preferred_username',
    'email_format' => '{email}',
    'identify_with_username' => '0',
    'link_existing_users' => '1',
    'create_if_does_not_exist' => '0',
    'alternate_redirect_uri' => '1',
));
update_option('openid_connect_generic_settings', $settings);
flush_rewrite_rules();
$result = activate_plugin($plugin);
if (is_wp_error($result)) {
    fwrite(STDERR, 'OIDC plugin activation failed: ' . $result->get_error_message() . "\n");
    exit(1);
}
echo "WordPress OIDC login button enabled; existing password login remains available\n";
