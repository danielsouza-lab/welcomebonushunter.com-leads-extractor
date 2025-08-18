<?php
/**
 * Plugin Name: Rolling Riches Leads API
 * Plugin URI: https://github.com/rolling-riches/leads-api
 * Description: Exposes sweeprewards signups data via REST API for external extraction
 * Version: 1.0.0
 * Author: Rolling Riches
 * License: Private
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Main plugin class
 */
class RollingRichesLeadsAPI {
    
    /**
     * Initialize the plugin
     */
    public function __construct() {
        add_action('rest_api_init', array($this, 'register_rest_routes'));
    }
    
    /**
     * Register REST API routes
     */
    public function register_rest_routes() {
        register_rest_route('rolling-riches/v1', '/leads', array(
            'methods' => 'GET',
            'callback' => array($this, 'get_leads'),
            'permission_callback' => array($this, 'check_permissions'),
            'args' => array(
                'since' => array(
                    'required' => false,
                    'type' => 'string',
                    'description' => 'Get leads since this date (Y-m-d H:i:s format)',
                ),
                'until' => array(
                    'required' => false,
                    'type' => 'string',
                    'description' => 'Get leads until this date (Y-m-d H:i:s format)',
                ),
                'last_id' => array(
                    'required' => false,
                    'type' => 'integer',
                    'description' => 'Get leads with ID greater than this (for incremental sync)',
                ),
                'limit' => array(
                    'required' => false,
                    'type' => 'integer',
                    'default' => 100,
                    'description' => 'Maximum number of leads to return',
                ),
                'offset' => array(
                    'required' => false,
                    'type' => 'integer',
                    'default' => 0,
                    'description' => 'Offset for pagination',
                ),
            ),
        ));
        
        register_rest_route('rolling-riches/v1', '/leads/stats', array(
            'methods' => 'GET',
            'callback' => array($this, 'get_stats'),
            'permission_callback' => array($this, 'check_permissions'),
        ));
    }
    
    /**
     * Check if user has permission to access the API
     */
    public function check_permissions() {
        // Require authentication
        if (!is_user_logged_in()) {
            return false;
        }
        
        // Check for administrator or editor role
        $user = wp_get_current_user();
        $allowed_roles = array('administrator', 'editor');
        
        if (array_intersect($allowed_roles, $user->roles)) {
            return true;
        }
        
        return false;
    }
    
    /**
     * Get sweeprewards signups data
     */
    public function get_leads($request) {
        global $wpdb;
        
        $since = $request->get_param('since');
        $until = $request->get_param('until');
        $last_id = intval($request->get_param('last_id'));
        $limit = intval($request->get_param('limit'));
        $offset = intval($request->get_param('offset'));
        
        // First, try to find the correct table
        // Common patterns for form data tables
        $possible_tables = array(
            $wpdb->prefix . 'sweeprewards_signups',
            $wpdb->prefix . 'sweepstakes_entries',
            $wpdb->prefix . 'contest_entries',
            $wpdb->prefix . 'form_submissions',
            $wpdb->prefix . 'cf7_data',
            $wpdb->prefix . 'wpforms_entries',
            $wpdb->prefix . 'frm_items',
            $wpdb->prefix . 'gf_entry',
            $wpdb->prefix . 'db7_forms',
        );
        
        $found_table = null;
        $leads = array();
        
        // Check which table exists
        foreach ($possible_tables as $table) {
            $table_exists = $wpdb->get_var("SHOW TABLES LIKE '$table'");
            if ($table_exists) {
                $found_table = $table;
                break;
            }
        }
        
        if ($found_table) {
            // Build query based on found table
            $query = "SELECT * FROM $found_table";
            $where_clauses = array();
            
            if ($since) {
                // Try common date column names
                $date_columns = array('created_at', 'date_created', 'submitted_at', 'entry_date', 'date', 'timestamp');
                $columns = $wpdb->get_col("SHOW COLUMNS FROM $found_table");
                
                foreach ($date_columns as $date_col) {
                    if (in_array($date_col, $columns)) {
                        $where_clauses[] = $wpdb->prepare("$date_col >= %s", $since);
                        break;
                    }
                }
            }
            
            if (!empty($where_clauses)) {
                $query .= " WHERE " . implode(" AND ", $where_clauses);
            }
            
            $query .= " ORDER BY id DESC";
            $query .= $wpdb->prepare(" LIMIT %d OFFSET %d", $limit, $offset);
            
            $results = $wpdb->get_results($query, ARRAY_A);
            
            if ($results) {
                foreach ($results as $row) {
                    $leads[] = $this->format_lead($row, $found_table);
                }
            }
        } else {
            // If no custom table found, try to get data from postmeta or options
            // This is a fallback for plugins that store data differently
            
            // Check if there's a custom post type for entries
            $args = array(
                'post_type' => array('sweepstakes_entry', 'form_submission', 'contest_entry'),
                'posts_per_page' => $limit,
                'offset' => $offset,
                'orderby' => 'date',
                'order' => 'DESC',
            );
            
            if ($since) {
                $args['date_query'] = array(
                    array(
                        'after' => $since,
                        'inclusive' => true,
                    ),
                );
            }
            
            $posts = get_posts($args);
            
            foreach ($posts as $post) {
                $meta = get_post_meta($post->ID);
                $leads[] = array(
                    'id' => $post->ID,
                    'date' => $post->post_date,
                    'title' => $post->post_title,
                    'data' => $meta,
                );
            }
        }
        
        // Also check for data in wp_options (some plugins store there)
        if (empty($leads)) {
            $option_keys = array(
                'sweeprewards_entries',
                'contest_submissions',
                'form_entries',
            );
            
            foreach ($option_keys as $key) {
                $data = get_option($key);
                if ($data && is_array($data)) {
                    $leads = array_merge($leads, $data);
                }
            }
        }
        
        return new WP_REST_Response(array(
            'success' => true,
            'found_table' => $found_table,
            'total' => count($leads),
            'leads' => $leads,
            'message' => $found_table ? "Data retrieved from $found_table" : "No sweeprewards table found, checked alternative sources",
        ), 200);
    }
    
    /**
     * Format lead data consistently
     */
    private function format_lead($row, $table_name) {
        $formatted = array(
            'id' => isset($row['id']) ? $row['id'] : null,
            'source' => $table_name,
        );
        
        // Map common field names
        $field_mappings = array(
            'email' => array('email', 'user_email', 'customer_email', 'mail'),
            'name' => array('name', 'full_name', 'user_name', 'customer_name', 'display_name'),
            'phone' => array('phone', 'telephone', 'mobile', 'phone_number'),
            'date' => array('created_at', 'date_created', 'submitted_at', 'entry_date', 'date', 'timestamp'),
        );
        
        foreach ($field_mappings as $standard_field => $possible_fields) {
            foreach ($possible_fields as $field) {
                if (isset($row[$field])) {
                    $formatted[$standard_field] = $row[$field];
                    break;
                }
            }
        }
        
        // Include all original data
        $formatted['raw_data'] = $row;
        
        return $formatted;
    }
    
    /**
     * Get statistics about leads
     */
    public function get_stats() {
        global $wpdb;
        
        $stats = array(
            'tables_checked' => array(),
            'leads_count' => 0,
        );
        
        // Check various possible tables
        $possible_tables = array(
            $wpdb->prefix . 'sweeprewards_signups',
            $wpdb->prefix . 'sweepstakes_entries',
            $wpdb->prefix . 'contest_entries',
            $wpdb->prefix . 'form_submissions',
        );
        
        foreach ($possible_tables as $table) {
            $exists = $wpdb->get_var("SHOW TABLES LIKE '$table'");
            if ($exists) {
                $count = $wpdb->get_var("SELECT COUNT(*) FROM $table");
                $stats['tables_checked'][$table] = array(
                    'exists' => true,
                    'count' => $count,
                );
                $stats['leads_count'] += $count;
            } else {
                $stats['tables_checked'][$table] = array(
                    'exists' => false,
                    'count' => 0,
                );
            }
        }
        
        // Also check all tables for reference
        $all_tables = $wpdb->get_results("SHOW TABLES", ARRAY_N);
        $stats['all_tables'] = array();
        
        foreach ($all_tables as $table) {
            $table_name = $table[0];
            // Look for tables that might contain form data
            if (strpos($table_name, 'form') !== false || 
                strpos($table_name, 'entry') !== false || 
                strpos($table_name, 'submission') !== false ||
                strpos($table_name, 'sweep') !== false ||
                strpos($table_name, 'contest') !== false ||
                strpos($table_name, 'lead') !== false) {
                
                $count = $wpdb->get_var("SELECT COUNT(*) FROM $table_name");
                $stats['all_tables'][$table_name] = $count;
            }
        }
        
        return new WP_REST_Response($stats, 200);
    }
}

// Initialize the plugin
new RollingRichesLeadsAPI();

// Add activation hook to flush rewrite rules
register_activation_hook(__FILE__, function() {
    flush_rewrite_rules();
});

// Add deactivation hook
register_deactivation_hook(__FILE__, function() {
    flush_rewrite_rules();
});