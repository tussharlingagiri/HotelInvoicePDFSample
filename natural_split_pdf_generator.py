"""
Generate hotel invoice PDF with natural cross-page record splitting (no indicators)
"""

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import random
from datetime import datetime, timedelta

def generate_fake_guest_data(num_guests=40):
    """Generate fake guest data"""
    
    first_names = ["John", "Sarah", "Michael", "Emma", "David", "Lisa", "Robert", "Anna", 
                   "James", "Maria", "William", "Jennifer", "Richard", "Patricia", "Thomas"]
    
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", 
                  "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson"]
    
    services = [
        ("Room Accommodation", 89.50),
        ("Breakfast Service", 15.00),
        ("WiFi Premium", 8.99),
        ("Parking Fee", 12.00),
        ("Minibar Charges", 25.50),
        ("Laundry Service", 18.75),
        ("Room Service", 32.00),
        ("Spa Treatment", 75.00),
        ("Business Center", 10.00),
        ("Late Checkout", 20.00),
        ("City Tax", 3.50),
        ("Telephone Charges", 7.25)
    ]
    
    guests = []
    base_date = datetime(2024, 11, 1)
    
    for i in range(num_guests):
        guest_name = f"{random.choice(first_names)} {random.choice(last_names)}"
        room_number = 100 + i
        check_in = base_date + timedelta(days=random.randint(0, 30))
        check_out = check_in + timedelta(days=random.randint(1, 5))
        
        # Generate 4-10 services per guest to ensure large tables
        guest_services = random.sample(services, random.randint(4, 10))
        
        guests.append({
            'name': guest_name,
            'room': str(room_number),
            'check_in': check_in.strftime('%d.%m.%Y'),
            'check_out': check_out.strftime('%d.%m.%Y'),
            'services': guest_services,
            'total': sum(price for _, price in guest_services)
        })
    
    return guests

def create_natural_split_pdf(filename='natural_split_hotel_invoice.pdf'):
    """Create PDF with natural cross-page record splitting (no continuation markers)"""
    
    doc = SimpleDocTemplate(filename, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    story.append(Paragraph("Grand Plaza Hotel Invoice", styles['Title']))
    story.append(Paragraph("Guest Services Report - November 2024", styles['Heading2']))
    story.append(Spacer(1, 30))
    
    guests = generate_fake_guest_data(40)
    
    page_height_used = 120  # Start with title space
    max_page_height = 680   # Usable page height
    split_guests = 0
    
    for guest_idx, guest in enumerate(guests):
        
        # Calculate space needed for complete guest record
        guest_header_space = 50
        service_table_space = 40 + (len(guest['services']) * 18) + 25  # Header + rows + total
        total_space_needed = guest_header_space + service_table_space
        
        # Force split if record won't fit on current page
        if page_height_used + total_space_needed > max_page_height:
            
            # Add guest header on current page
            guest_header = f"Guest: {guest['name']}, Room: {guest['room']}, Stay: {guest['check_in']} to {guest['check_out']}"
            story.append(Paragraph(guest_header, styles['Heading3']))
            story.append(Spacer(1, 15))
            
            # Add services table header only
            story.append(Paragraph("Services and Charges:", styles['Heading4']))
            header_table = Table([['Service Description', 'Tax Rate', 'Qty', 'Unit Price', 'Total Price']], 
                                colWidths=[2.8*inch, 0.7*inch, 0.5*inch, 1*inch, 1*inch])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(header_table)
            
            # Natural page break (no indicators)
            story.append(PageBreak())
            
            # Continue services on next page (looks natural)
            service_data = []
            for service_name, price in guest['services']:
                tax_rate = "19%" if "Room" in service_name else "7%"
                quantity = random.randint(1, 2)
                unit_price = f"€{price:.2f}"
                total_price = f"€{price * quantity:.2f}"
                service_data.append([service_name, tax_rate, str(quantity), unit_price, total_price])
            
            # Add total row
            service_data.append(['TOTAL', '', '', '', f"€{guest['total']:.2f}"])
            
            # Services table on new page
            services_table = Table(service_data, colWidths=[2.8*inch, 0.7*inch, 0.5*inch, 1*inch, 1*inch])
            services_table.setStyle(TableStyle([
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(services_table)
            story.append(Spacer(1, 25))
            
            split_guests += 1
            page_height_used = len(guest['services']) * 18 + 80  # Reset for new page
            
        else:
            # Complete guest record on same page
            guest_header = f"Guest: {guest['name']}, Room: {guest['room']}, Stay: {guest['check_in']} to {guest['check_out']}"
            story.append(Paragraph(guest_header, styles['Heading3']))
            story.append(Spacer(1, 15))
            
            # Complete services table
            service_data = [['Service Description', 'Tax Rate', 'Qty', 'Unit Price', 'Total Price']]
            
            for service_name, price in guest['services']:
                tax_rate = "19%" if "Room" in service_name else "7%"
                quantity = random.randint(1, 2)
                unit_price = f"€{price:.2f}"
                total_price = f"€{price * quantity:.2f}"
                service_data.append([service_name, tax_rate, str(quantity), unit_price, total_price])
            
            service_data.append(['TOTAL', '', '', '', f"€{guest['total']:.2f}"])
            
            table = Table(service_data, colWidths=[2.8*inch, 0.7*inch, 0.5*inch, 1*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(table)
            story.append(Spacer(1, 25))
            
            page_height_used += total_space_needed
    
    # Build PDF
    doc.build(story)
    print(f"✅ Generated {filename} with natural cross-page record splitting")
    print(f"📄 {split_guests} guests split across pages (no continuation markers)")
    return filename

def test_natural_generator():
    """Test the natural split PDF generator"""
    print("🏨 Generating Natural Cross-Page Hotel Invoice PDF")
    print("=" * 55)
    
    filename = create_natural_split_pdf()
    
    print(f"\n📊 Natural Split PDF Details:")
    print(f"   File: {filename}")
    print(f"   Guests: 40 guests")
    print(f"   Features: Natural cross-page record splitting")
    print(f"   Pattern: Guest header on page N, services naturally continue on page N+1")
    print(f"   No continuation markers or indicators")
    
    print(f"\n🔧 Test the chunker:")
    print(f"   python large_test_chunker.py")

if __name__ == "__main__":
    test_natural_generator()
