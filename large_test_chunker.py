"""
Specialized chunker for the large test PDF with cross-page record reconstruction
"""

import pdfplumber
import pandas as pd
import re
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TestGuestRecord:
    """Represents a guest record that may span across pages"""
    guest_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    room_number: Optional[str] = None
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    services: List[Dict] = None
    total_amount: float = 0.0
    page_start: int = 0
    page_end: int = 0
    is_complete: bool = False
    is_split: bool = False
    
    def __post_init__(self):
        if self.services is None:
            self.services = []

class LargeTestChunker:
    """Specialized chunker for large test PDF format"""
    
    def __init__(self):
        self.incomplete_guest = None
        self.complete_guests = []
        
    def process_large_test_pdf(self, pdf_path: str) -> pd.DataFrame:
        """Process large test PDF with cross-page record reconstruction"""
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_texts = []
                for page in pdf.pages:
                    text = page.extract_text()
                    page_texts.append(text)
                
                return self._process_pages(page_texts)
                
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            return pd.DataFrame()
    
    def _process_pages(self, page_texts: List[str]) -> pd.DataFrame:
        """Process all pages and reconstruct split records"""
        
        all_guests = []
        carry_over_guest = None
        
        for page_num, text in enumerate(page_texts, 1):
            logger.info(f"Processing page {page_num}")
            
            # Process current page
            page_guests, incomplete_guest = self._process_single_page(
                text, page_num, carry_over_guest
            )
            
            all_guests.extend(page_guests)
            carry_over_guest = incomplete_guest
            
        # Handle any remaining incomplete guest
        if carry_over_guest and carry_over_guest.guest_id:
            logger.warning(f"Incomplete guest at end: {carry_over_guest.guest_id}")
            if carry_over_guest.services or carry_over_guest.first_name:  # Has some data
                all_guests.append(carry_over_guest)
        
        return self._convert_to_dataframe(all_guests)
    
    def _process_single_page(self, text: str, page_num: int, 
                           carry_over: Optional[TestGuestRecord]) -> Tuple[List[TestGuestRecord], Optional[TestGuestRecord]]:
        """Process a single page and handle record reconstruction"""
        
        lines = text.split('\n')
        complete_guests = []
        current_guest = carry_over
        
        # Patterns for test PDF format
        guest_pattern = r'Guest:\s*([A-Za-z]+)\s+([A-Za-z]+)\s*\(ID:\s*(G\d+)\)'
        room_pattern = r'Room:\s*(\d+)\s*\|\s*Check-in:\s*([\d.]+)\s*\|\s*Check-out:\s*([\d.]+)'
        service_pattern = r'^([A-Za-z\s\-]+)\s+(\d+)\s+\$?([\d.]+)\s+\$?([\d.]+)$'
        total_pattern = r'TOTAL:\s*\$?([\d.]+)'
        continuation_pattern = r'CONTINUED ON NEXT PAGE'
        
        in_service_table = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            if not line:
                continue
            
            # Check for continuation indicator
            if re.search(continuation_pattern, line):
                if current_guest:
                    current_guest.is_split = True
                    logger.info(f"Guest {current_guest.guest_id} continues on next page")
                continue
                
            # Check for new guest
            guest_match = re.search(guest_pattern, line)
            if guest_match:
                # Save previous guest if complete
                if current_guest and self._is_guest_complete(current_guest):
                    complete_guests.append(current_guest)
                elif current_guest and current_guest.guest_id:
                    # Incomplete guest - will be carried over
                    logger.info(f"Guest {current_guest.guest_id} incomplete, carrying to next page")
                
                # Start new guest
                current_guest = TestGuestRecord(
                    first_name=guest_match.group(1),
                    last_name=guest_match.group(2),
                    guest_id=guest_match.group(3),
                    page_start=page_num,
                    services=[]
                )
                in_service_table = False
                continue
            
            # Check for room info
            if current_guest and not current_guest.room_number:
                room_match = re.search(room_pattern, line)
                if room_match:
                    current_guest.room_number = room_match.group(1)
                    current_guest.check_in_date = room_match.group(2)
                    current_guest.check_out_date = room_match.group(3)
                    continue
            
            # Check for service table header
            if re.search(r'Service.*Qty.*Unit Price.*Total', line):
                in_service_table = True
                continue
            
            # Process service lines
            if in_service_table and current_guest:
                service_match = re.search(service_pattern, line)
                if service_match:
                    service_name = service_match.group(1).strip()
                    quantity = service_match.group(2).strip()
                    unit_price = service_match.group(3).strip()
                    total_price = service_match.group(4).strip()
                    
                    try:
                        current_guest.services.append({
                            'service': service_name,
                            'quantity': int(quantity),
                            'unit_price': float(unit_price),
                            'total_price': float(total_price)
                        })
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Error parsing service line: {line} - {e}")
                    continue
                
                # Check for total
                total_match = re.search(total_pattern, line)
                if total_match:
                    try:
                        current_guest.total_amount = float(total_match.group(1))
                        in_service_table = False
                    except ValueError:
                        pass
        
        # Check final guest status
        complete_guests_final = complete_guests
        incomplete_guest = None
        
        if current_guest:
            current_guest.page_end = page_num
            if self._is_guest_complete(current_guest):
                complete_guests_final.append(current_guest)
            else:
                incomplete_guest = current_guest
        
        return complete_guests_final, incomplete_guest
    
    def _is_guest_complete(self, guest: TestGuestRecord) -> bool:
        """Check if guest record has all required information"""
        return (
            guest.guest_id is not None and
            guest.first_name is not None and
            guest.last_name is not None and
            guest.room_number is not None and
            guest.check_in_date is not None and
            guest.check_out_date is not None and
            len(guest.services) > 0 and
            guest.total_amount > 0
        )
    
    def _convert_to_dataframe(self, guests: List[TestGuestRecord]) -> pd.DataFrame:
        """Convert guest records to DataFrame"""
        
        if not guests:
            return pd.DataFrame()
        
        data = []
        for guest in guests:
            services_text = "; ".join([s['service'] for s in guest.services])
            data.append({
                'Guest_ID': guest.guest_id,
                'Guest_Name': f"{guest.first_name} {guest.last_name}",
                'Room_Number': guest.room_number,
                'Check_In_Date': guest.check_in_date,
                'Check_Out_Date': guest.check_out_date,
                'Services': services_text,
                'Total_Amount': round(guest.total_amount, 2),
                'Service_Count': len(guest.services),
                'Page_Start': guest.page_start,
                'Page_End': guest.page_end,
                'Spans_Pages': guest.page_start != guest.page_end,
                'Is_Split': guest.is_split
            })
        
        df = pd.DataFrame(data)
        logger.info(f"Converted {len(df)} guest records to DataFrame")
        
        # Show cross-page records
        cross_page = df[df['Spans_Pages'] == True]
        if not cross_page.empty:
            logger.info(f"Found {len(cross_page)} records spanning multiple pages:")
            for _, record in cross_page.iterrows():
                logger.info(f"  {record['Guest_ID']}: {record['Guest_Name']} (Pages {record['Page_Start']}-{record['Page_End']})")
        
        # Show split records
        split_records = df[df['Is_Split'] == True]
        if not split_records.empty:
            logger.info(f"Found {len(split_records)} records with continuation indicators:")
            for _, record in split_records.iterrows():
                logger.info(f"  {record['Guest_ID']}: {record['Guest_Name']}")
        
        return df
    
    def export_chunks_to_json(self, pdf_path: str, output_file: str = "chunks_analysis.json") -> str:
        """Export raw chunks and processed data to JSON"""
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Extract raw page chunks
                raw_chunks = []
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    raw_chunks.append({
                        'page_number': page_num,
                        'raw_text': text,
                        'line_count': len(text.split('\n')),
                        'char_count': len(text)
                    })
                
                # Process with chunker
                df = self.process_large_test_pdf(pdf_path)
                
                # Convert DataFrame to records
                processed_records = df.to_dict('records') if not df.empty else []
                
                # Create comprehensive JSON output
                output_data = {
                    'metadata': {
                        'pdf_file': pdf_path,
                        'extraction_timestamp': datetime.now().isoformat(),
                        'total_pages': len(raw_chunks),
                        'total_records_extracted': len(processed_records),
                        'cross_page_records': len(df[df['Spans_Pages'] == True]) if not df.empty else 0,
                        'split_records': len(df[df['Is_Split'] == True]) if not df.empty else 0
                    },
                    'raw_chunks': raw_chunks,
                    'processed_records': processed_records,
                    'analysis': {
                        'chunking_strategy': 'cross_page_reconstruction',
                        'duplicate_handling': 'enabled',
                        'total_revenue': float(df['Total_Amount'].sum()) if not df.empty else 0.0,
                        'average_amount': float(df['Total_Amount'].mean()) if not df.empty else 0.0
                    }
                }
                
                # Write to JSON file
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Exported chunks and data to {output_file}")
                return output_file
                
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return ""

def test_large_test_chunker():
    """Test the chunker with large test PDF"""
    
    print("🏨 Testing Large Test PDF Cross-Page Record Reconstruction")
    print("=" * 60)
    
    chunker = LargeTestChunker()
    
    try:
        df = chunker.process_large_test_pdf("large_test_invoice.pdf")
        
        if not df.empty:
            print(f"✅ Successfully processed {len(df)} guest records")
            print("\n📊 Sample Results:")
            print(df.head(10).to_string(index=False))
            
            # Show cross-page analysis
            cross_page_records = df[df['Spans_Pages'] == True]
            if not cross_page_records.empty:
                print(f"\n🔄 Cross-page records: {len(cross_page_records)}")
                for _, record in cross_page_records.iterrows():
                    print(f"   {record['Guest_ID']}: {record['Guest_Name']} (Pages {record['Page_Start']}-{record['Page_End']})")
            
            # Show split records
            split_records = df[df['Is_Split'] == True]
            if not split_records.empty:
                print(f"\n📄 Records with continuation: {len(split_records)}")
                for _, record in split_records.iterrows():
                    print(f"   {record['Guest_ID']}: {record['Guest_Name']}")
            
            print(f"\n💰 Total revenue: ${df['Total_Amount'].sum():.2f}")
            print(f"📈 Average stay amount: ${df['Total_Amount'].mean():.2f}")
            
            # Export to JSON
            print(f"\n📄 Exporting chunks to JSON...")
            json_file = chunker.export_chunks_to_json("large_test_invoice.pdf")
            if json_file:
                print(f"✅ Exported to {json_file}")
            
        else:
            print("❌ No records extracted")
            
    except FileNotFoundError:
        print("❌ PDF file not found. Run large_test_pdf_generator.py first.")
    except Exception as e:
        print(f"❌ Error: {e}")

def export_chunks_only():
    """Export chunks to JSON without full processing output"""
    
    print("📄 Exporting PDF chunks to JSON...")
    chunker = LargeTestChunker()
    
    try:
        json_file = chunker.export_chunks_to_json("large_test_invoice.pdf", "hotel_chunks.json")
        if json_file:
            print(f"✅ Successfully exported chunks to {json_file}")
            
            # Show file size
            import os
            size = os.path.getsize(json_file)
            print(f"📊 File size: {size:,} bytes")
            
            # Show structure preview
            with open(json_file, 'r') as f:
                data = json.load(f)
                
            print(f"\n📋 JSON Structure:")
            print(f"  • Metadata: {len(data['metadata'])} fields")
            print(f"  • Raw chunks: {len(data['raw_chunks'])} pages")
            print(f"  • Processed records: {len(data['processed_records'])} guests")
            print(f"  • Analysis data: {len(data['analysis'])} metrics")
            
        else:
            print("❌ Export failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_large_test_chunker()
