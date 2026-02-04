import streamlit as st
import xml.etree.ElementTree as ET
import os
import re
from datetime import datetime
import pandas as pd

# Set page configuration
st.set_page_config(
    page_title="JATS XML Validator",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #374151;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #D1FAE5;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #10B981;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #FEE2E2;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #EF4444;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #FEF3C7;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #F59E0B;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #DBEAFE;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #3B82F6;
        margin: 1rem 0;
    }
    .type-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.875rem;
        font-weight: 500;
        margin-right: 0.5rem;
    }
    .table-badge {
        background-color: #E0F2FE;
        color: #0369A1;
    }
    .figure-badge {
        background-color: #FCE7F3;
        color: #9D174D;
    }
    .issue-item {
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
        background-color: #F9FAFB;
        border-left: 4px solid #6B7280;
    }
</style>
""", unsafe_allow_html=True)

class JATSValidator:
    def __init__(self):
        self.namespaces = {'xlink': 'http://www.w3.org/1999/xlink'}
    
    def extract_filename_pattern(self, xml_filename):
        """Extract the base pattern from XML filename."""
        base_name = os.path.splitext(xml_filename)[0]
        pattern_match = re.match(r'([A-Za-z]+-\d+-\d+-\d+)', base_name)
        if pattern_match:
            return pattern_match.group(1)
        return base_name
    
    def validate_xml_file(self, xml_content, filename):
        """Validate JATS XML content including tables and figures."""
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            
            # Register xlink namespace
            ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
            
            # Extract expected pattern from filename
            expected_pattern = self.extract_filename_pattern(filename)
            
            validation_results = {
                'filename': filename,
                'expected_pattern': expected_pattern,
                'tables_found': 0,
                'figures_found': 0,
                'total_table_images': 0,
                'total_figure_images': 0,
                'issues': {
                    'table_duplicates': [],
                    'figure_duplicates': [],
                    'table_refs': [],
                    'figure_refs': [],
                    'naming': [],
                    'table_sequence': [],
                    'figure_sequence': [],
                    'fig_id_duplicates': [],
                    'table_id_duplicates': []
                },
                'table_details': {},
                'figure_details': {},
                'all_table_image_ids': [],
                'all_figure_image_ids': [],
                'all_fig_ids': [],
                'all_table_ids': []
            }
            
            # ===== VALIDATE TABLES =====
            table_wraps = root.findall('.//table-wrap')
            validation_results['tables_found'] = len(table_wraps)
            
            for table_wrap in table_wraps:
                table_id = table_wrap.get('id', 'unknown')
                
                # Check for duplicate table IDs
                if table_id != 'unknown':
                    validation_results['all_table_ids'].append(table_id)
                
                table_element = table_wrap.find('.//table')
                
                if table_element is None:
                    continue
                
                # Get image IDs from this table
                image_ids = []
                for graphic in table_element.findall('.//graphic'):
                    href = graphic.get('{http://www.w3.org/1999/xlink}href')
                    if href:
                        img_filename = os.path.basename(href)
                        base_name = os.path.splitext(img_filename)[0]
                        image_ids.append(base_name)
                
                validation_results['table_details'][table_id] = {
                    'image_count': len(image_ids),
                    'images': image_ids,
                    'type': 'table'
                }
                validation_results['total_table_images'] += len(image_ids)
                validation_results['all_table_image_ids'].extend(image_ids)
                
                # Check for duplicate image IDs within table
                seen = set()
                duplicates = []
                for img_id in image_ids:
                    if img_id in seen:
                        duplicates.append(img_id)
                    seen.add(img_id)
                
                if duplicates:
                    for dup in set(duplicates):
                        count = image_ids.count(dup)
                        validation_results['issues']['table_duplicates'].append({
                            'element_type': 'table',
                            'element_id': table_id,
                            'image_id': dup,
                            'count': count
                        })
                
                # Check table references
                for img_id in image_ids:
                    img_match = re.search(r'_T(\d+)-F', img_id)
                    if img_match:
                        img_table_num = img_match.group(1)
                        
                        table_match = re.search(r'T(\d+)', table_id)
                        if table_match:
                            table_num = table_match.group(1)
                            
                            if img_table_num != table_num:
                                validation_results['issues']['table_refs'].append({
                                    'element_type': 'table',
                                    'element_id': table_id,
                                    'image_id': img_id,
                                    'referenced_table': f'T{img_table_num}'
                                })
                
                # Check table image sequence numbering
                pattern = r'F(\d+)$'
                numbers = []
                for img_id in image_ids:
                    match = re.search(pattern, img_id)
                    if match:
                        numbers.append(int(match.group(1)))
                
                if numbers:
                    numbers.sort()
                    expected_sequence = list(range(min(numbers), max(numbers) + 1))
                    if numbers != expected_sequence:
                        missing = list(set(expected_sequence) - set(numbers))
                        validation_results['issues']['table_sequence'].append({
                            'element_type': 'table',
                            'element_id': table_id,
                            'missing_numbers': missing,
                            'actual_numbers': numbers
                        })
            
            # ===== VALIDATE FIGURES =====
            figs = root.findall('.//fig')
            validation_results['figures_found'] = len(figs)
            
            for fig in figs:
                fig_id = fig.get('id', 'unknown')
                
                # Check for duplicate figure IDs
                if fig_id != 'unknown':
                    validation_results['all_fig_ids'].append(fig_id)
                
                # Get image from figure
                graphic = fig.find('.//graphic')
                if graphic is not None:
                    href = graphic.get('{http://www.w3.org/1999/xlink}href')
                    if href:
                        img_filename = os.path.basename(href)
                        base_name = os.path.splitext(img_filename)[0]
                        
                        validation_results['figure_details'][fig_id] = {
                            'image_count': 1,
                            'images': [base_name],
                            'type': 'figure'
                        }
                        validation_results['total_figure_images'] += 1
                        validation_results['all_figure_image_ids'].append(base_name)
                        
                        # Check figure image naming
                        img_match = re.match(r'([A-Za-z]+-\d+-\d+-\d+)_F(\d+)', base_name)
                        if img_match:
                            img_pattern = img_match.group(1)
                            fig_num = img_match.group(2)
                            
                            # Check naming consistency
                            if img_pattern != expected_pattern:
                                validation_results['issues']['naming'].append({
                                    'element_type': 'figure',
                                    'element_id': fig_id,
                                    'image_id': base_name,
                                    'actual_pattern': img_pattern,
                                    'expected_pattern': expected_pattern
                                })
                            
                            # Check if figure number matches fig ID
                            fig_id_match = re.search(r'F(\d+)', fig_id)
                            if fig_id_match:
                                actual_fig_num = fig_id_match.group(1)
                                if actual_fig_num != fig_num:
                                    validation_results['issues']['figure_refs'].append({
                                        'element_type': 'figure',
                                        'element_id': fig_id,
                                        'image_id': base_name,
                                        'referenced_fig': f'F{fig_num}',
                                        'actual_fig': f'F{actual_fig_num}'
                                    })
            
            # ===== CHECK FOR DUPLICATE FIGURE IMAGES =====
            # Check for duplicate figure image IDs
            figure_seen = set()
            figure_duplicates = []
            for img_id in validation_results['all_figure_image_ids']:
                if img_id in figure_seen:
                    figure_duplicates.append(img_id)
                figure_seen.add(img_id)
            
            if figure_duplicates:
                for dup in set(figure_duplicates):
                    count = validation_results['all_figure_image_ids'].count(dup)
                    # Find which figures have this duplicate
                    dup_figs = []
                    for fig_id, details in validation_results['figure_details'].items():
                        if dup in details['images']:
                            dup_figs.append(fig_id)
                    
                    validation_results['issues']['figure_duplicates'].append({
                        'element_type': 'figure',
                        'image_id': dup,
                        'count': count,
                        'figures': dup_figs
                    })
            
            # ===== CHECK NAMING FOR TABLE IMAGES =====
            for img_id in validation_results['all_table_image_ids']:
                img_match = re.match(r'([A-Za-z]+-\d+-\d+-\d+)_', img_id)
                if img_match:
                    img_pattern = img_match.group(1)
                    if img_pattern != expected_pattern:
                        # Find which table has this image
                        table_with_image = None
                        for table_id, details in validation_results['table_details'].items():
                            if img_id in details['images']:
                                table_with_image = table_id
                                break
                        
                        validation_results['issues']['naming'].append({
                            'element_type': 'table',
                            'element_id': table_with_image or 'unknown',
                            'image_id': img_id,
                            'actual_pattern': img_pattern,
                            'expected_pattern': expected_pattern
                        })
            
            # ===== CHECK FOR DUPLICATE FIG IDs =====
            fig_id_counts = {}
            for fig_id in validation_results['all_fig_ids']:
                fig_id_counts[fig_id] = fig_id_counts.get(fig_id, 0) + 1
            
            for fig_id, count in fig_id_counts.items():
                if count > 1:
                    validation_results['issues']['fig_id_duplicates'].append({
                        'id': fig_id,
                        'count': count
                    })
            
            # ===== CHECK FOR DUPLICATE TABLE IDs =====
            table_id_counts = {}
            for table_id in validation_results['all_table_ids']:
                table_id_counts[table_id] = table_id_counts.get(table_id, 0) + 1
            
            for table_id, count in table_id_counts.items():
                if count > 1:
                    validation_results['issues']['table_id_duplicates'].append({
                        'id': table_id,
                        'count': count
                    })
            
            # ===== CHECK FIGURE SEQUENCE =====
            # Extract figure numbers from fig IDs
            fig_numbers = []
            for fig_id in validation_results['all_fig_ids']:
                match = re.search(r'F(\d+)', fig_id)
                if match:
                    fig_numbers.append(int(match.group(1)))
            
            if fig_numbers:
                fig_numbers.sort()
                expected_fig_sequence = list(range(min(fig_numbers), max(fig_numbers) + 1))
                if fig_numbers != expected_fig_sequence:
                    missing_figs = list(set(expected_fig_sequence) - set(fig_numbers))
                    validation_results['issues']['figure_sequence'].append({
                        'element_type': 'figures',
                        'missing_numbers': missing_figs,
                        'actual_numbers': fig_numbers
                    })
            
            # Determine overall success
            has_issues = any(len(issues) > 0 for issues in validation_results['issues'].values())
            validation_results['success'] = not has_issues
            
            return validation_results
            
        except ET.ParseError as e:
            return {
                'success': False,
                'message': f"XML parsing error: {str(e)}",
                'details': {}
            }
        except Exception as e:
            return {
                'success': False,
                'message': f"Error: {str(e)}",
                'details': {}
            }

def main():
    # Initialize validator
    validator = JATSValidator()
    
    # Title
    st.markdown('<h1 class="main-header">📄 JATS XML Validator</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #6B7280; font-size: 1.1rem;">Validate Tables, Figures, and Image IDs in JATS XML files</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Validation Settings")
        
        st.subheader("📊 Table Checks:")
        check_table_duplicates = st.checkbox("Check duplicate table image IDs", value=True)
        check_table_refs = st.checkbox("Check table references", value=True)
        check_table_sequence = st.checkbox("Check table image sequence", value=True)
        check_table_id_duplicates = st.checkbox("Check duplicate table IDs", value=True)
        
        st.subheader("🖼️ Figure Checks:")
        check_figure_duplicates = st.checkbox("Check duplicate figure image IDs", value=True)
        check_figure_refs = st.checkbox("Check figure references", value=True)
        check_figure_sequence = st.checkbox("Check figure ID sequence", value=True)
        check_fig_id_duplicates = st.checkbox("Check duplicate figure IDs", value=True)
        
        st.subheader("📝 Common Checks:")
        check_naming = st.checkbox("Check naming consistency", value=True)
        
        st.divider()
        
        st.subheader("📤 Upload XML Files")
        uploaded_files = st.file_uploader(
            "Choose JATS XML files",
            type=['xml'],
            accept_multiple_files=True,
            help="Upload one or more JATS XML files for validation"
        )
        
        st.divider()
        
        if st.button("🧹 Clear All", type="secondary", width='stretch'):
            st.rerun()
    
    # Main content area
    if uploaded_files:
        # Process each file
        all_results = []
        
        for uploaded_file in uploaded_files:
            # Read file content
            xml_content = uploaded_file.read().decode('utf-8')
            
            # Create tabs for each file
            tab1, tab2, tab3 = st.tabs([
                f"📄 {uploaded_file.name}",
                "📊 Summary",
                "📋 All Elements"
            ])
            
            with tab1:
                # Validate the file
                with st.spinner(f"Validating {uploaded_file.name}..."):
                    result = validator.validate_xml_file(xml_content, uploaded_file.name)
                
                # Display overall stats
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Tables Found", result['tables_found'])
                
                with col2:
                    st.metric("Figures Found", result['figures_found'])
                
                with col3:
                    st.metric("Table Images", result['total_table_images'])
                
                with col4:
                    if result.get('success', False):
                        st.metric("Status", "✅ PASS", delta="No issues")
                    else:
                        st.metric("Status", "❌ FAIL", delta="Issues found", delta_color="inverse")
                
                st.divider()
                
                # Display issues
                if not result.get('success', True):
                    issues_found = False
                    
                    # TABLE ISSUES
                    if (check_table_duplicates and result['issues']['table_duplicates']) or \
                       (check_table_refs and result['issues']['table_refs']) or \
                       (check_table_sequence and result['issues']['table_sequence']) or \
                       (check_table_id_duplicates and result['issues']['table_id_duplicates']):
                        
                        issues_found = True
                        with st.expander("📊 Table Issues", expanded=True):
                            # Duplicate table image IDs
                            if check_table_duplicates and result['issues']['table_duplicates']:
                                st.error("**Duplicate Table Image IDs:**")
                                for issue in result['issues']['table_duplicates']:
                                    st.error(f"<span class='type-badge table-badge'>Table</span> **{issue['element_id']}**: `{issue['image_id']}` appears {issue['count']} times", unsafe_allow_html=True)
                            
                            # Wrong table references
                            if check_table_refs and result['issues']['table_refs']:
                                st.error("**Wrong Table References:**")
                                for issue in result['issues']['table_refs']:
                                    st.error(f"<span class='type-badge table-badge'>Table</span> **{issue['element_id']}** contains `{issue['image_id']}` which references **Table {issue['referenced_table']}**", unsafe_allow_html=True)
                            
                            # Table sequence issues
                            if check_table_sequence and result['issues']['table_sequence']:
                                st.warning("**Table Image Sequence Issues:**")
                                for issue in result['issues']['table_sequence']:
                                    st.warning(f"<span class='type-badge table-badge'>Table</span> **{issue['element_id']}**: Missing numbers {issue['missing_numbers']}", unsafe_allow_html=True)
                            
                            # Duplicate table IDs
                            if check_table_id_duplicates and result['issues']['table_id_duplicates']:
                                st.error("**Duplicate Table IDs:**")
                                for issue in result['issues']['table_id_duplicates']:
                                    st.error(f"Table ID `{issue['id']}` appears {issue['count']} times")
                    
                    # FIGURE ISSUES
                    if (check_figure_duplicates and result['issues']['figure_duplicates']) or \
                       (check_figure_refs and result['issues']['figure_refs']) or \
                       (check_figure_sequence and result['issues']['figure_sequence']) or \
                       (check_fig_id_duplicates and result['issues']['fig_id_duplicates']):
                        
                        issues_found = True
                        with st.expander("🖼️ Figure Issues", expanded=True):
                            # Duplicate figure image IDs
                            if check_figure_duplicates and result['issues']['figure_duplicates']:
                                st.error("**Duplicate Figure Image IDs:**")
                                for issue in result['issues']['figure_duplicates']:
                                    st.error(f"<span class='type-badge figure-badge'>Figure</span> `{issue['image_id']}` appears {issue['count']} times in figures: {', '.join(issue['figures'])}", unsafe_allow_html=True)
                            
                            # Wrong figure references
                            if check_figure_refs and result['issues']['figure_refs']:
                                st.error("**Wrong Figure References:**")
                                for issue in result['issues']['figure_refs']:
                                    st.error(f"<span class='type-badge figure-badge'>Figure</span> **{issue['element_id']}** contains `{issue['image_id']}` which references **Figure {issue['referenced_fig']}** but should be **{issue['actual_fig']}**", unsafe_allow_html=True)
                            
                            # Figure sequence issues
                            if check_figure_sequence and result['issues']['figure_sequence']:
                                st.warning("**Figure ID Sequence Issues:**")
                                for issue in result['issues']['figure_sequence']:
                                    st.warning(f"<span class='type-badge figure-badge'>Figures</span> Missing figure numbers {issue['missing_numbers']}", unsafe_allow_html=True)
                            
                            # Duplicate figure IDs
                            if check_fig_id_duplicates and result['issues']['fig_id_duplicates']:
                                st.error("**Duplicate Figure IDs:**")
                                for issue in result['issues']['fig_id_duplicates']:
                                    st.error(f"Figure ID `{issue['id']}` appears {issue['count']} times")
                    
                    # NAMING ISSUES (both tables and figures)
                    if check_naming and result['issues']['naming']:
                        issues_found = True
                        with st.expander("📝 Naming Consistency Issues", expanded=True):
                            st.warning(f"**Expected pattern**: `{result['expected_pattern']}`")
                            for issue in result['issues']['naming']:
                                badge_class = "table-badge" if issue['element_type'] == 'table' else "figure-badge"
                                st.error(f"<span class='type-badge {badge_class}'>{issue['element_type'].title()}</span> **{issue['element_id']}**: `{issue['image_id']}` uses `{issue['actual_pattern']}`, should be `{issue['expected_pattern']}`", unsafe_allow_html=True)
                    
                    if not issues_found:
                        st.success("✅ No issues found in the selected checks!")
                else:
                    st.success("✅ All validation checks passed!")
            
            with tab2:
                # Show summary tables
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 Tables Summary")
                    if result['table_details']:
                        table_data = []
                        for table_id, details in result['table_details'].items():
                            table_data.append({
                                'Table ID': table_id,
                                'Images': details['image_count'],
                                'First Image': details['images'][0] if details['images'] else 'N/A',
                                'Last Image': details['images'][-1] if details['images'] else 'N/A'
                            })
                        
                        df_tables = pd.DataFrame(table_data)
                        st.dataframe(df_tables, width='stretch')
                    else:
                        st.info("No tables found")
                
                with col2:
                    st.subheader("🖼️ Figures Summary")
                    if result['figure_details']:
                        figure_data = []
                        for fig_id, details in result['figure_details'].items():
                            figure_data.append({
                                'Figure ID': fig_id,
                                'Image': details['images'][0] if details['images'] else 'N/A'
                            })
                        
                        df_figures = pd.DataFrame(figure_data)
                        st.dataframe(df_figures, width='stretch')
                    else:
                        st.info("No figures found")
                
                # Charts
                if result['table_details'] or result['figure_details']:
                    st.subheader("📈 Distribution")
                    
                    chart_data = {
                        'Type': ['Tables', 'Figures'],
                        'Count': [result['tables_found'], result['figures_found']],
                        'Images': [result['total_table_images'], result['total_figure_images']]
                    }
                    
                    df_chart = pd.DataFrame(chart_data)
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.bar_chart(df_chart.set_index('Type')['Count'])
                    
                    with col2:
                        st.bar_chart(df_chart.set_index('Type')['Images'])
            
            with tab3:
                # Show all image IDs by type
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 Table Image IDs")
                    if result['all_table_image_ids']:
                        for img_id in sorted(set(result['all_table_image_ids'])):
                            st.code(img_id, language=None)
                    else:
                        st.info("No table images found")
                
                with col2:
                    st.subheader("🖼️ Figure Image IDs")
                    if result['all_figure_image_ids']:
                        for img_id in sorted(set(result['all_figure_image_ids'])):
                            st.code(img_id, language=None)
                    else:
                        st.info("No figure images found")
            
            # Store result for batch summary
            all_results.append({
                'filename': uploaded_file.name,
                'success': result.get('success', False),
                'tables': result['tables_found'],
                'figures': result['figures_found'],
                'table_images': result['total_table_images'],
                'figure_images': result['total_figure_images'],
                'issues': sum(len(issues) for issues in result['issues'].values())
            })
        
        # Batch summary
        if len(uploaded_files) > 1:
            st.divider()
            st.subheader("📊 Batch Validation Summary")
            
            summary_df = pd.DataFrame(all_results)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Files", len(all_results))
            
            with col2:
                passed = sum(1 for r in all_results if r['success'])
                st.metric("Passed", passed)
            
            with col3:
                failed = len(all_results) - passed
                st.metric("Failed", failed)
            
            with col4:
                if len(all_results) > 0:
                    success_rate = (passed / len(all_results)) * 100
                    st.metric("Success Rate", f"{success_rate:.1f}%")
            
            # Detailed table
            st.dataframe(summary_df, width='stretch', hide_index=True)
            
            # Download results
            if st.button("📥 Download Validation Report", width='stretch'):
                report = "JATS XML Validation Report\n"
                report += "=" * 60 + "\n"
                report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"Files processed: {len(all_results)}\n"
                report += f"Validation checks: Tables & Figures\n"
                report += "=" * 60 + "\n\n"
                
                for result in all_results:
                    status = "✅ PASS" if result['success'] else "❌ FAIL"
                    report += f"{status} - {result['filename']}\n"
                    report += f"  Tables: {result['tables']}, Figures: {result['figures']}\n"
                    report += f"  Table Images: {result['table_images']}, Figure Images: {result['figure_images']}\n"
                    report += f"  Total Issues: {result['issues']}\n\n"
                
                st.download_button(
                    label="Click to download report",
                    data=report,
                    file_name=f"jats_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
    
    else:
        # Welcome screen when no files uploaded
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.image("https://cdn-icons-png.flaticon.com/512/136/136526.png", width=150)
            st.markdown("""
            <div class="info-box">
            <h3>Welcome to JATS XML Validator</h3>
            <p>This tool validates both <strong>Tables</strong> and <strong>Figures</strong> in JATS XML files:</p>
            
            <h4>📊 Table Validation:</h4>
            <ul>
                <li>Check for duplicate image IDs within tables</li>
                <li>Verify table references are correct</li>
                <li>Validate sequential numbering (F1, F2, F3...)</li>
                <li>Check for duplicate table IDs</li>
            </ul>
            
            <h4>🖼️ Figure Validation:</h4>
            <ul>
                <li>Check for duplicate figure image IDs</li>
                <li>Verify figure references match image names</li>
                <li>Check figure ID sequence (F1, F2, F3...)</li>
                <li>Check for duplicate figure IDs</li>
            </ul>
            
            <h4>📝 Common Validation:</h4>
            <ul>
                <li>Ensure naming consistency (e.g., JCS-41-4-694 pattern)</li>
                <li>Validate all images match filename pattern</li>
            </ul>
            
            <p><b>How to use:</b></p>
            <ol>
                <li>Upload XML files using the sidebar</li>
                <li>Configure validation checks (Tables/Figures)</li>
                <li>View detailed results with color-coded badges</li>
                <li>Download comprehensive validation reports</li>
            </ol>
            </div>
            """, unsafe_allow_html=True)
            
            # Example XML snippets
            with st.expander("📝 Examples of JATS XML Elements"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Table Example:**")
                    st.code("""<table-wrap id="T1">
    <table>
        <tr>
            <td><graphic xlink:href="JCS-41-4-694_T1-F1.tif"/></td>
            <td><graphic xlink:href="JCS-41-4-694_T1-F2.tif"/></td>
        </tr>
    </table>
</table-wrap>""", language="xml")
                
                with col2:
                    st.markdown("**Figure Example:**")
                    st.code("""<fig id="F1" position="float">
    <label>Figure 1</label>
    <graphic xlink:href="JCS-41-4-694_F1.tif"/>
</fig>""", language="xml")

if __name__ == "__main__":
    main()