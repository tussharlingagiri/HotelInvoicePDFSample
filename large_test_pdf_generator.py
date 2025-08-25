"""
Generate a 10-page hotel invoice PDF with fake data that demonstrates cross-page record splitting
"""

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import random
from datetime import datetime, timedelta

def generate_fake_guest_data(num_guests=150):
    """Generate fake guest data with realistic names and services"""
    
    first_names = [
        "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason", "Isabella", "William",
        "Mia", "James", "Charlotte", "Benjamin", "Amelia", "Lucas", "Harper", "Henry", "Evelyn", "Alexander",
        "Abigail", "Michael", "Emily", "Daniel", "Elizabeth", "Jacob", "Sofia", "Logan", "Avery", "Jackson",
        "Ella", "Sebastian", "Madison", "Jack", "Scarlett", "Aiden", "Victoria", "Owen", "Aria", "Samuel"
    ]
    
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson"
    ]
    
    services = [
        ("Room Rate - Standard", 89.00, 120.00),
        ("Room Rate - Deluxe", 129.00, 180.00),
        ("Room Rate - Suite", 199.00, 299.00),
        ("Breakfast", 15.50, 25.00),
        ("Parking", 12.00, 18.00),
        ("WiFi Premium", 8.00, 12.00),
        ("Minibar", 25.00, 45.00),
        ("Room Service", 18.00, 35.00),
        ("Laundry Service", 22.00, 40.00),
        ("Spa Treatment", 75.00, 150.00),
        ("City Tax", 2.50, 4.00),
        ("Resort Fee", 25.00, 35.00)
    ]
    
    guests = []
    base_date = datetime(2024, 11, 1)
    
    for i in range(num_guests):
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        
        check_in = base_date + timedelta(days=random.randint(0, 30))
        nights = random.randint(1, 7)
        check_out = check_in + timedelta(days=nights)
        
        room_number = 100 + i + random.randint(1, 50)
        
        # Generate services for this guest
        guest_services = []
        num_services = random.randint(3, 8)
        selected_services = random.sample(services, num_services)
        
        total_amount = 0.0
        for service_name, min_price, max_price in selected_services:
            price = round(random.uniform(min_price, max_price), 2)
            quantity = 1 if "Room Rate" in service_name else random.randint(1, nights)
            total_price = round(price * quantity, 2)
            total_amount += total_price
            
            guest_services.append({
                'service': service_name,
                'quantity': quantity,
                'unit_price': price,
                'total_price': total_price
            })
        
        guests.append({
            'guest_id': f"G{i+1:04d}",
            'first_name': first_name,
            'last_name': last_name,
            'room_number': room_number,
            'check_in': check_in.strftime("%d.%m.%Y"),
            'check_out': check_out.strftime("%d.%m.%Y"),
            'services': guest_services,
            'total_amount': round(total_amount, 2)
        })
    
    return guests

def create_large_test_pdf(filename='large_test_invoice.pdf'):
    """Create a 10-page PDF with cross-page record splitting"""
    
    print(f"🏨 Generating {filename} with cross-page record splitting...")
    
    doc = SimpleDocTemplate(filename, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=20,
        alignment=1  # Center
    )
    
    # Generate guest data
    guests = generate_fake_guest_data(150)
    
    # Hotel header
    story.append(Paragraph("Grand Plaza Hotel Invoice", title_style))
    story.append(Paragraph("123 Hotel Street, City Center", styles['Normal']))
    story.append(Paragraph("Phone: +1-555-0123 | Email: billing@grandplaza.com", styles['Normal']))
    story.append(Spacer(1, 20))
    
    current_guest_index = 0
    page_num = 1
    
    while current_guest_index < len(guests) and page_num <= 10:
        print(f"📄 Processing page {page_num}...")
        
        # Page header
        story.append(Paragraph(f"Invoice Details - Page {page_num}", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        # Determine how many complete guests fit on this page
        guests_on_page = []
        remaining_space = 25  # Approximate lines per page
        
        while current_guest_index < len(guests) and remaining_space > 0:
            guest = guests[current_guest_index]
            
            # Calculate space needed for this guest
            guest_header_lines = 3  # Guest info header
            service_lines = len(guest['services']) + 2  # Services + header + total
            guest_total_lines = guest_header_lines + service_lines + 2  # Extra spacing
            
            # If guest fits completely, add it
            if guest_total_lines <= remaining_space:
                guests_on_page.append(guest)
                remaining_space -= guest_total_lines
                current_guest_index += 1
            
            # If guest doesn't fit, create a split scenario
            elif remaining_space >= 5:  # Minimum space for partial guest
                # Split the guest: info on this page, services on next page
                partial_guest = guest.copy()
                partial_guest['services'] = []  # No services on this page
                partial_guest['split_indicator'] = "CONTINUED ON NEXT PAGE"
                guests_on_page.append(partial_guest)
                
                # Mark this guest for continuation
                guests[current_guest_index]['continuation'] = True
                break
            else:
                # Not enough space, move to next page
                break
        
        # Create content for this page
        for guest in guests_on_page:
            # Guest header
            guest_info = [
                f"Guest: {guest['first_name']} {guest['last_name']} (ID: {guest['guest_id']})",
                f"Room: {guest['room_number']} | Check-in: {guest['check_in']} | Check-out: {guest['check_out']}"
            ]
            
            for info in guest_info:
                story.append(Paragraph(info, styles['Normal']))
            
            story.append(Spacer(1, 8))
            
            # Services table
            if guest['services']:
                service_data = [['Service', 'Qty', 'Unit Price', 'Total']]
                for service in guest['services']:
                    service_data.append([
                        service['service'],
                        str(service['quantity']),
                        f"${service['unit_price']:.2f}",
                        f"${service['total_price']:.2f}"
                    ])
                
                # Add total row
                service_data.append(['', '', 'TOTAL:', f"${guest['total_amount']:.2f}"])
                
                table = Table(service_data, colWidths=[3*inch, 0.8*inch, 1*inch, 1*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(table)
            
            elif 'split_indicator' in guest:
                story.append(Paragraph(f"⚠️ {guest['split_indicator']}", styles['Normal']))
            
            story.append(Spacer(1, 15))
        
        # Add page break if not the last page
        if page_num < 10 and current_guest_index < len(guests):
            story.append(PageBreak())
        
        page_num += 1
    
    # Build the PDF
    doc.build(story)
    
    print(f"✅ Generated {filename}")
    print(f"📊 Total guests: {len(guests)}")
    print(f"📄 Pages: 10")
    
    # Count split records
    split_count = sum(1 for guest in guests if guest.get('continuation', False))
    print(f"🔄 Cross-page splits: {split_count}")
    
    return filename

def test_large_pdf():
    """Test the large PDF generation"""
    
    print("🏨 Testing Large Hotel Invoice PDF Generation")
    print("=" * 50)
    
    filename = create_large_test_pdf()
    
    print(f"\n✅ Successfully created {filename}")
    print("\n📋 Features demonstrated:")
    print("  • 10-page hotel invoice")
    print("  • ~150 guest records")
    print("  • Cross-page record splitting")
    print("  • Realistic service data")
    print("  • Guest info + services separation")
    
    print(f"\n🔧 Next steps:")
    print("  1. Test with pdf_extractor.py")
    print("  2. Test with hotel_invoice_chunker.py")
    print("  3. Verify cross-page reconstruction")

if __name__ == "__main__":
    test_large_pdf()
