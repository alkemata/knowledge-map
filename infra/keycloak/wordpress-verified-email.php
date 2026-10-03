<?php
/**
 * Plugin Name: Alkemata OIDC account-linking guard
 * Description: Allow OpenID Connect login only for verified Keycloak email identities.
 */

add_filter('openid-connect-generic-user-login-test', static function ($allowed, $claim) {
    return $allowed && is_array($claim) && !empty($claim['email_verified']);
}, 10, 2);

add_filter('openid-connect-generic-user-creation-test', static function () {
    // The first migration links existing WordPress users and retains their roles.
    return false;
}, 10, 2);
