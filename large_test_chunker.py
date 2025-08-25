"""
Chunker for large test hotel invoice PDFs with cross-page record reconstruction
"""

import pdfplumber
import pandas as pd
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TestGuestRecord:
    """Represents a guest record that may span across pages"""
    guest_name: Optional[str] = None
    room_number: Optional[str] = None
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    services: List[Dict] = None
    total_amount: float = 0.0
    page_start: int = 0
    page_end: int = 0
    is_complete: bool = False
    
    def __post_init__(self):
        if self.services is None:
            self.services = []

class LargeTestChunker:
    """Chunker for large test hotel invoice format"""
    
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
        if carry_over_guest and carry_over_guest.guest_name:
            logger.warning(f"Incomplete guest at end: {carry_over_guest.guest_name}")
            if carry_over_guest.services:  # Has some data
                all_guests.append(carry_over_guest)
        
        return self._convert_to_dataframe(all_guests)
    
    def _process_single_page(self, text: str, page_num: int, 
                           carry_over: Optional[TestGuestRecord]) -> Tuple[List[TestGuestRecord], Optional[TestGuestRecord]]:
        """Process a single page and handle record reconstruction"""
        
        lines = text.split('\n')
        complete_guests = []
        current_guest = carry_over
        
        # Patterns for test hotel format
        guest_pattern = r'Guest:\s*([^,]+),\s*Room:\s*(\d+),\s*Stay:\s*(\d{1,2}\.\d{1,2}\.\d{4})\s*to\s*(\d{1,2}\.\d{1,2}\.\d{4})'
        service_pattern = r'^([A-Za-z\s]+)\s+([\d%]+)\s+(\d+)\s+€([\d.]+)\s+€([\d.]+)$'
        total_pattern = r'^TOTAL\s+€([\d.]+)$'
        services_header_pattern = r'Services and Charges:'
        
        in_service_table = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            if not line:
                continue
                
            # Check for new guest
            guest_match = re.search(guest_pattern, line)
            if guest_match:
                # Save previous guest if complete
                if current_guest and self._is_guest_complete(current_guest):
                    complete_guests.append(current_guest)
                elif current_guest and current_guest.guest_name:
                    # Incomplete guest - will be carried over
                    logger.info(f"Guest {current_guest.guest_name} incomplete, carrying to next page")
                
                # Start new guest
                current_guest = TestGuestRecord(
                    guest_name=guest_match.group(1).strip(),
                    room_number=guest_match.group(2),
                    check_in_date=guest_match.group(3),
                    check_out_date=guest_match.group(4),
                    page_start=page_num,
                    services=[]
                )
                in_service_table = False
                continue
            
            # Check for service table header
            if 'Service Description' in line and 'Total Price' in line:
                in_service_table = True
                continue
            
            # Check for services header
            if re.search(services_header_pattern, line):
                in_service_table = True
                continue
            
            # Process service lines
            if in_service_table and current_guest:
                service_match = re.search(service_pattern, line)
                if service_match:
                    service_name = service_match.group(1).strip()
                    tax_rate = service_match.group(2).strip()
                    quantity = service_match.group(3).strip()
                    unit_price = service_match.group(4)
                    total_price = service_match.group(5)
                    
                    try:
                        current_guest.services.append({
                            'service': service_name,
                            'tax_rate': tax_rate,
                            'quantity': int(quantity),
                            'unit_price': float(unit_price),
                            'total_price': float(total_price)
                        })
                        current_guest.total_amount += float(total_price)
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Error parsing service line: {line} - {e}")
                
                # Check for total line
                total_match = re.search(total_pattern, line)
                if total_match and current_guest:
                    current_guest.total_amount = float(total_match.group(1))
                    current_guest.is_complete = True
        
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
            guest.guest_name is not None and
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
                'Guest_Name': guest.guest_name,
                'Room_Number': guest.room_number,
                'Check_In_Date': guest.check_in_date,
                'Check_Out_Date': guest.check_out_date,
                'Services': services_text,
                'Total_Amount': round(guest.total_amount, 2),
                'Service_Count': len(guest.services),
                'Page_Start': guest.page_start,
                'Page_End': guest.page_end,
                'Spans_Pages': guest.page_start != guest.page_end
            })
        
        df = pd.DataFrame(data)
        logger.info(f"Converted {len(df)} guest records to DataFrame")
        
        # Show cross-page records
        cross_page = df[df['Spans_Pages'] == True]
        if not cross_page.empty:
            logger.info(f"Found {len(cross_page)} records spanning multiple pages:")
            for _, record in cross_page.iterrows():
                logger.info(f"  {record['Guest_Name']} (Pages {record['Page_Start']}-{record['Page_End']})")
        
        return df

def test_large_chunker():
    """Test the chunker with large test PDF"""
    
    print("🏨 Testing Large Hotel Invoice Cross-Page Record Reconstruction")
    print("=" * 70)
    
    chunker = LargeTestChunker()
    
    try:
        df = chunker.process_large_test_pdf("natural_split_hotel_invoice.pdf")
        
        if not df.empty:
            print(f"✅ Successfully processed {len(df)} guest records")
            
            # Show summary statistics
            print(f"\n📊 Processing Results:")
            print(f"   Total Guests: {len(df)}")
            print(f"   Total Revenue: €{df['Total_Amount'].sum():.2f}")
            print(f"   Avg Services per Guest: {df['Service_Count'].mean():.1f}")
            
            # Show cross-page analysis
            cross_page_records = df[df['Spans_Pages'] == True]
            if not cross_page_records.empty:
                print(f"\n🔄 Cross-page records: {len(cross_page_records)}")
                for _, record in cross_page_records.iterrows():
                    print(f"   {record['Guest_Name']}: Pages {record['Page_Start']}-{record['Page_End']}")
            
            # Save results as JSON
            guest_records = df.to_dict('records')
            
            # Create comprehensive JSON output
            json_output = {
                'extraction_summary': {
                    'total_guests': len(df),
                    'cross_page_guests': len(cross_page_records),
                    'total_revenue': float(df['Total_Amount'].sum()),
                    'avg_services_per_guest': float(df['Service_Count'].mean()),
                    'extraction_timestamp': pd.Timestamp.now().isoformat()
                },
                'cross_page_analysis': {
                    'cross_page_rate': f"{(len(cross_page_records)/len(df)*100):.1f}%",
                    'cross_page_details': cross_page_records[['Guest_Name', 'Room_Number', 'Page_Start', 'Page_End', 'Total_Amount']].to_dict('records')
                },
                'guest_records': guest_records,
                'chunking_metadata': {
                    'chunking_strategy': 'cross_page_reconstruction',
                    'pdf_source': 'natural_split_hotel_invoice.pdf',
                    'pages_processed': len([text for text in page_texts if text.strip()]) if 'page_texts' in locals() else 'unknown'
                }
            }
            
            with open('hotel_chunks.json', 'w') as f:
                json.dump(json_output, f, indent=2)
            print(f"\n💾 Complete results saved to: hotel_chunks.json")
            print(f"📊 JSON contains {len(guest_records)} guest records with cross-page analysis")
            
        else:
            print("❌ No records extracted")
            
    except FileNotFoundError:
        print("❌ PDF file not found. Run large_test_pdf_generator.py first.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_large_chunker()
