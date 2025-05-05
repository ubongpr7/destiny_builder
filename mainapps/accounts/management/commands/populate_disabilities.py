from django.core.management.base import BaseCommand
from django.db import transaction
from ...models import Disability  # Adjust the import path as needed

class Command(BaseCommand):
    help = 'Populates the database with a comprehensive list of disabilities'

    def handle(self, *args, **options):
        disabilities_data = [
            {
                "name": "Visual Impairment",
                "description": "Includes blindness, low vision, and color blindness. Affects a person's ability to see clearly even with corrective lenses."
            },
            {
                "name": "Hearing Impairment",
                "description": "Includes deafness and hard of hearing. Affects a person's ability to hear sounds partially or completely."
            },
            {
                "name": "Mobility Impairment",
                "description": "Affects a person's ability to move freely, may include paralysis, amputation, or conditions affecting coordination."
            },
            {
                "name": "Cognitive Disability",
                "description": "Affects cognitive functions such as thinking, concentrating, reading, learning, and memory."
            },
            {
                "name": "Speech Impairment",
                "description": "Affects a person's ability to produce speech that is clear and understandable."
            },
            {
                "name": "Autism Spectrum Disorder",
                "description": "A developmental disorder that affects communication, social interaction, and behavior."
            },
            {
                "name": "Down Syndrome",
                "description": "A genetic disorder causing developmental and intellectual delays."
            },
            {
                "name": "Cerebral Palsy",
                "description": "A group of disorders affecting movement, balance, and posture."
            },
            {
                "name": "Multiple Sclerosis",
                "description": "A disease that affects the central nervous system, disrupting the flow of information between the brain and body."
            },
            {
                "name": "Parkinson's Disease",
                "description": "A progressive nervous system disorder affecting movement."
            },
            {
                "name": "Epilepsy",
                "description": "A neurological disorder characterized by recurrent seizures."
            },
            {
                "name": "Muscular Dystrophy",
                "description": "A group of diseases causing progressive weakness and loss of muscle mass."
            },
            {
                "name": "Spinal Cord Injury",
                "description": "Damage to the spinal cord resulting in partial or complete loss of motor control and sensation."
            },
            {
                "name": "Traumatic Brain Injury",
                "description": "An injury to the brain caused by external force, affecting cognitive, physical, and psychological functions."
            },
            {
                "name": "Spina Bifida",
                "description": "A birth defect where the spine and spinal cord don't form properly."
            },
            {
                "name": "Cystic Fibrosis",
                "description": "A genetic disorder affecting the lungs, digestive system, and other organs."
            },
            {
                "name": "Chronic Fatigue Syndrome",
                "description": "A complex disorder characterized by extreme fatigue that can't be explained by any underlying medical condition."
            },
            {
                "name": "Fibromyalgia",
                "description": "A disorder characterized by widespread musculoskeletal pain accompanied by fatigue, sleep, memory and mood issues."
            },
            {
                "name": "Rheumatoid Arthritis",
                "description": "An autoimmune and inflammatory disease affecting joints and other body systems."
            },
            {
                "name": "Lupus",
                "description": "A systemic autoimmune disease that occurs when the body's immune system attacks its own tissues and organs."
            },
            {
                "name": "Crohn's Disease",
                "description": "An inflammatory bowel disease causing inflammation of the digestive tract."
            },
            {
                "name": "Ulcerative Colitis",
                "description": "An inflammatory bowel disease causing inflammation and ulcers in the digestive tract."
            },
            {
                "name": "Diabetes",
                "description": "A group of diseases that result in too much sugar in the blood."
            },
            {
                "name": "Heart Disease",
                "description": "Various conditions affecting the heart's structure and functions."
            },
            {
                "name": "Chronic Obstructive Pulmonary Disease (COPD)",
                "description": "A chronic inflammatory lung disease causing obstructed airflow from the lungs."
            },
            {
                "name": "Asthma",
                "description": "A condition in which airways narrow and swell and may produce extra mucus."
            },
            {
                "name": "Sickle Cell Disease",
                "description": "A group of inherited red blood cell disorders."
            },
            {
                "name": "Hemophilia",
                "description": "A rare disorder in which blood doesn't clot normally."
            },
            {
                "name": "HIV/AIDS",
                "description": "A chronic, potentially life-threatening condition caused by the human immunodeficiency virus (HIV)."
            },
            {
                "name": "Cancer",
                "description": "A disease in which abnormal cells divide uncontrollably and destroy body tissue."
            },
            {
                "name": "Post-Traumatic Stress Disorder (PTSD)",
                "description": "A mental health condition triggered by experiencing or witnessing a terrifying event."
            },
            {
                "name": "Major Depressive Disorder",
                "description": "A mental health disorder characterized by persistently depressed mood or loss of interest in activities."
            },
            {
                "name": "Bipolar Disorder",
                "description": "A mental health condition that causes extreme mood swings."
            },
            {
                "name": "Schizophrenia",
                "description": "A serious mental disorder in which people interpret reality abnormally."
            },
            {
                "name": "Obsessive-Compulsive Disorder (OCD)",
                "description": "A disorder characterized by unreasonable thoughts and fears that lead to repetitive behaviors."
            },
            {
                "name": "Attention Deficit Hyperactivity Disorder (ADHD)",
                "description": "A chronic condition including attention difficulty, hyperactivity, and impulsiveness."
            },
            {
                "name": "Dyslexia",
                "description": "A learning disorder that involves difficulty reading."
            },
            {
                "name": "Dyscalculia",
                "description": "A learning disorder that affects a person's ability to understand numbers and learn math facts."
            },
            {
                "name": "Dysgraphia",
                "description": "A learning disorder that affects a person's ability to write coherently."
            },
            {
                "name": "Tourette Syndrome",
                "description": "A disorder that involves repetitive movements or unwanted sounds that can't be easily controlled."
            },
            {
                "name": "Albinism",
                "description": "A group of inherited disorders characterized by little or no melanin production."
            },
            {
                "name": "Dwarfism",
                "description": "A medical or genetic condition that causes someone to be considerably shorter than average."
            },
            {
                "name": "Amyotrophic Lateral Sclerosis (ALS)",
                "description": "A progressive nervous system disease affecting nerve cells in the brain and spinal cord, causing loss of muscle control."
            },
            {
                "name": "Huntington's Disease",
                "description": "A progressive brain disorder caused by a defective gene."
            },
            {
                "name": "Narcolepsy",
                "description": "A chronic sleep disorder characterized by overwhelming daytime drowsiness and sudden attacks of sleep."
            },
            {
                "name": "Chronic Pain",
                "description": "Pain that persists or recurs for more than 3 months."
            },
            {
                "name": "Ehlers-Danlos Syndromes",
                "description": "A group of disorders affecting connective tissues that support skin, bones, blood vessels, and other organs and tissues."
            },
            {
                "name": "Marfan Syndrome",
                "description": "A genetic disorder affecting the body's connective tissue."
            },
            {
                "name": "Osteogenesis Imperfecta",
                "description": "A group of genetic disorders that mainly affect the bones, also known as brittle bone disease."
            },
            {
                "name": "Prader-Willi Syndrome",
                "description": "A rare genetic disorder that causes obesity, intellectual disability, and shortness in height."
            },
            {
                "name": "Rett Syndrome",
                "description": "A rare genetic neurological and developmental disorder affecting brain development."
            },
            {
                "name": "Williams Syndrome",
                "description": "A developmental disorder that affects many parts of the body."
            },
            {
                "name": "Angelman Syndrome",
                "description": "A genetic disorder causing developmental disabilities and neurological problems."
            },
            {
                "name": "Fragile X Syndrome",
                "description": "A genetic condition causing intellectual disability, behavioral and learning challenges."
            },
            {
                "name": "Klinefelter Syndrome",
                "description": "A genetic condition affecting males due to an extra X chromosome."
            },
            {
                "name": "Turner Syndrome",
                "description": "A genetic condition affecting females due to complete or partial absence of the second X chromosome."
            },
            {
                "name": "Aphasia",
                "description": "A condition that affects the ability to communicate, often as a result of brain damage."
            },
            {
                "name": "Apraxia",
                "description": "A motor disorder caused by damage to the brain, affecting the ability to perform movements and gestures."
            },
            {
                "name": "Dysarthria",
                "description": "A motor speech disorder resulting from neurological injury."
            },
            {
                "name": "Stuttering",
                "description": "A speech disorder involving disruptions in the flow of speech."
            },
            {
                "name": "Vertigo",
                "description": "A sensation of feeling off balance or dizzy."
            },
            {
                "name": "Meniere's Disease",
                "description": "An inner ear disorder that causes episodes of vertigo."
            },
            {
                "name": "Tinnitus",
                "description": "The perception of noise or ringing in the ears."
            },
            {
                "name": "Usher Syndrome",
                "description": "A genetic disorder causing hearing loss and vision loss."
            },
            {
                "name": "Retinitis Pigmentosa",
                "description": "A group of rare, genetic disorders that involve a breakdown and loss of cells in the retina."
            },
            {
                "name": "Macular Degeneration",
                "description": "A medical condition which may result in blurred or no vision in the center of the visual field."
            },
            {
                "name": "Glaucoma",
                "description": "A group of eye conditions that damage the optic nerve."
            },
            {
                "name": "Cataracts",
                "description": "A clouding of the normally clear lens of the eye."
            },
            {
                "name": "Amblyopia",
                "description": "A vision development disorder in which an eye fails to achieve normal visual acuity."
            },
            {
                "name": "Strabismus",
                "description": "A condition in which the eyes do not properly align with each other when looking at an object."
            },
            {
                "name": "Nystagmus",
                "description": "Involuntary eye movement that may result in reduced or limited vision."
            },
            {
                "name": "Dysphagia",
                "description": "Difficulty swallowing."
            },
            {
                "name": "Gastroparesis",
                "description": "A condition that affects the normal spontaneous movement of the muscles in the stomach."
            },
            {
                "name": "Irritable Bowel Syndrome (IBS)",
                "description": "A common disorder that affects the large intestine."
            },
            {
                "name": "Celiac Disease",
                "description": "A serious autoimmune disease where the ingestion of gluten leads to damage in the small intestine."
            },
            {
                "name": "Chronic Kidney Disease",
                "description": "A condition characterized by a gradual loss of kidney function over time."
            },
            {
                "name": "Polycystic Kidney Disease",
                "description": "An inherited disorder in which clusters of cysts develop primarily within the kidneys."
            },
            {
                "name": "Addison's Disease",
                "description": "A disorder in which the adrenal glands don't produce enough hormones."
            },
            {
                "name": "Cushing's Syndrome",
                "description": "A condition that occurs when the body is exposed to high levels of the hormone cortisol for a long time."
            },
            {
                "name": "Hypothyroidism",
                "description": "A condition in which the thyroid gland doesn't produce enough thyroid hormone."
            },
            {
                "name": "Hyperthyroidism",
                "description": "A condition in which the thyroid gland produces too much thyroid hormone."
            },
            {
                "name": "Osteoporosis",
                "description": "A bone disease that occurs when the body loses too much bone, makes too little bone, or both."
            },
            {
                "name": "Osteoarthritis",
                "description": "A type of joint disease that results from breakdown of joint cartilage and underlying bone."
            },
            {
                "name": "Ankylosing Spondylitis",
                "description": "An inflammatory disease that can cause some of the vertebrae in the spine to fuse."
            },
            {
                "name": "Psoriatic Arthritis",
                "description": "A form of arthritis affecting some people who have psoriasis."
            },
            {
                "name": "Gout",
                "description": "A form of inflammatory arthritis characterized by recurrent attacks of a red, tender, hot, and swollen joint."
            },
            {
                "name": "Sjogren's Syndrome",
                "description": "An immune system disorder characterized by dry eyes and dry mouth."
            },
            {
                "name": "Raynaud's Phenomenon",
                "description": "A condition where blood flow to fingers, toes, ears, or nose is limited in response to cold or stress."
            },
            {
                "name": "Scleroderma",
                "description": "A group of rare diseases that involve hardening and tightening of the skin and connective tissues."
            },
            {
                "name": "Vasculitis",
                "description": "A group of disorders that destroy blood vessels by inflammation."
            },
            {
                "name": "Myasthenia Gravis",
                "description": "A chronic autoimmune neuromuscular disease characterized by varying degrees of weakness of the skeletal muscles."
            },
            {
                "name": "Guillain-Barré Syndrome",
                "description": "A rare disorder in which the body's immune system attacks the nerves."
            },
            {
                "name": "Chronic Inflammatory Demyelinating Polyneuropathy",
                "description": "A neurological disorder characterized by progressive weakness and impaired sensory function in the legs and arms."
            },
            {
                "name": "Charcot-Marie-Tooth Disease",
                "description": "A group of inherited disorders that cause nerve damage, leading to smaller, weaker muscles."
            },
            {
                "name": "Friedreich's Ataxia",
                "description": "A rare inherited disease that causes progressive damage to the nervous system."
            },
            {
                "name": "Ataxia Telangiectasia",
                "description": "A rare, neurodegenerative, inherited disease causing severe disability."
            },
            {
                "name": "Spinal Muscular Atrophy",
                "description": "A genetic disease affecting the central nervous system, peripheral nervous system, and voluntary muscle movement."
            },
            {
                "name": "Limb-Girdle Muscular Dystrophy",
                "description": "A group of disorders affecting the voluntary muscles, primarily around the hips and shoulders."
            },
            {
                "name": "Facioscapulohumeral Muscular Dystrophy",
                "description": "A genetic muscle disorder that initially affects the muscles of the face, shoulders, and upper arms."
            },
            {
                "name": "Myotonic Dystrophy",
                "description": "A form of muscular dystrophy that affects muscles and many other organs in the body."
            },
            {
                "name": "Becker Muscular Dystrophy",
                "description": "A genetic disorder characterized by progressive muscle weakness in the legs and pelvis."
            },
            {
                "name": "Duchenne Muscular Dystrophy",
                "description": "A genetic disorder characterized by progressive muscle degeneration and weakness."
            },
            {
                "name": "Congenital Myopathy",
                "description": "A group of muscle disorders present at birth characterized by weakness and hypotonia."
            },
            {
                "name": "Mitochondrial Myopathy",
                "description": "A group of neuromuscular diseases caused by damage to the mitochondria."
            },
            {
                "name": "Polymyositis",
                "description": "An inflammatory disease of the muscles characterized by muscle weakness."
            },
            {
                "name": "Dermatomyositis",
                "description": "An inflammatory disease characterized by muscle weakness and a skin rash."
            },
            {
                "name": "Inclusion Body Myositis",
                "description": "An inflammatory muscle disease characterized by muscle inflammation, weakness, and atrophy."
            },
        ]

        self.stdout.write("Starting to populate disabilities...")
        
        created_count = 0
        existing_count = 0
        
        with transaction.atomic():
            for disability_data in disabilities_data:
                disability, created = Disability.objects.get_or_create(
                    name=disability_data["name"],
                    defaults={"description": disability_data.get("description", "")}
                )
                
                if created:
                    created_count += 1
                else:
                    existing_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f"Successfully populated disabilities! "
            f"Created: {created_count}, Already existed: {existing_count}"
        ))