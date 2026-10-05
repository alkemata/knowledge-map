<?php
/**
 * Plugin Name: Alkemata Private Statistics Bridge
 * Description: Read-only aggregate WP Statistics data for the private Alkemata dashboard.
 */

if (!defined('ABSPATH')) {
    exit;
}

add_action('rest_api_init', function () {
    register_rest_route('alkemata-analytics/v1', '/summary', array(
        'methods' => 'GET',
        'permission_callback' => function (WP_REST_Request $request) {
            $header = $request->get_header('authorization');
            $expected = get_option('alkemata_analytics_token_hash', '');
            if (!is_string($header) || !preg_match('/^Bearer ([A-Za-z0-9_-]{32,256})$/', $header, $match)
                || !is_string($expected) || strlen($expected) !== 64
                || !hash_equals($expected, hash('sha256', $match[1]))) {
                return new WP_Error('alkemata_stats_forbidden', 'Statistics access denied.', array('status' => 403));
            }
            return true;
        },
        'callback' => function (WP_REST_Request $request) {
            global $wpdb;
            $days = max(1, min(90, (int) $request->get_param('days')));
            $today = wp_date('Y-m-d');
            $since = (new DateTimeImmutable($today, wp_timezone()))
                ->modify('-' . ($days - 1) . ' days')->format('Y-m-d');
            $summary = $wpdb->prefix . 'statistics_summary_totals';
            $pages = $wpdb->prefix . 'statistics_pages';
            $posts = $wpdb->posts;
            foreach (array($summary, $pages, $posts) as $table) {
                if (!preg_match('/^[A-Za-z0-9_]+$/', $table)) {
                    return new WP_Error('alkemata_stats_table', 'Invalid statistics table.', array('status' => 500));
                }
            }
            $daily = $wpdb->get_results($wpdb->prepare(
                "SELECT date, visitors, views FROM `{$summary}` WHERE date >= %s AND date <= %s ORDER BY date",
                $since, $today
            ), ARRAY_A);
            if ($wpdb->last_error) {
                return new WP_Error('alkemata_stats_query', 'Statistics unavailable.', array('status' => 503));
            }
            $daily = array_map(function ($row) {
                return array('date' => $row['date'], 'visitors' => (int) $row['visitors'], 'views' => (int) $row['views']);
            }, $daily);
            // WP Statistics summarizes completed days; use its live functions for today.
            if (function_exists('wp_statistics_visit') && function_exists('wp_statistics_visitor')) {
                $today_row = array('date' => $today,
                    'visitors' => (int) wp_statistics_visitor('today'),
                    'views' => (int) wp_statistics_visit('today'));
                $last = count($daily) - 1;
                if ($last >= 0 && $daily[$last]['date'] === $today) {
                    $daily[$last] = $today_row;
                } else {
                    $daily[] = $today_row;
                }
            }
            $top = $wpdb->get_results($wpdb->prepare(
                "SELECT p.ID AS post_id, p.post_title AS title, SUM(s.count) AS views
                 FROM `{$pages}` s INNER JOIN `{$posts}` p ON p.ID = s.id
                 WHERE s.date >= %s AND s.date <= %s
                   AND p.post_status = 'publish' AND p.post_type IN ('post', 'page')
                 GROUP BY p.ID, p.post_title ORDER BY views DESC LIMIT 10",
                $since, $today
            ), ARRAY_A);
            if ($wpdb->last_error) {
                return new WP_Error('alkemata_stats_query', 'Statistics unavailable.', array('status' => 503));
            }
            $top = array_map(function ($row) {
                return array('post_id' => (int) $row['post_id'],
                    'title' => $row['title'], 'views' => (int) $row['views']);
            }, $top);
            $response = rest_ensure_response(array(
                'source' => 'WP Statistics', 'period_days' => $days,
                'visitors' => array_sum(array_column($daily, 'visitors')),
                'views' => array_sum(array_column($daily, 'views')),
                'daily' => $daily, 'top_pages' => $top,
                'updated_at' => gmdate('c'),
            ));
            $response->header('Cache-Control', 'private, no-store');
            return $response;
        },
        'args' => array('days' => array('default' => 7, 'sanitize_callback' => 'absint')),
    ));
});
