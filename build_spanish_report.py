from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_HTML = ROOT / "output" / "selvanova_competitive_report.html"
TARGET_HTML = ROOT / "output" / "selvanova_competitive_report_es.html"


def inject_chart_styling(html: str) -> str:
    marker = """    .caption {
      font-size: 12px;
      color: var(--muted);
      margin-top: 8px;
    }"""
    replacement = """    .caption {
      font-size: 12px;
      color: var(--muted);
      margin-top: 8px;
    }
    .chart-card {
      position: relative;
      overflow: hidden;
      background-size: cover;
      background-position: center;
      background-repeat: no-repeat;
      isolation: isolate;
    }
    .chart-card::before {
      content: "";
      position: absolute;
      inset: 0;
      z-index: 0;
      pointer-events: none;
      background: linear-gradient(180deg, rgba(255, 248, 240, 0.84), rgba(255, 251, 245, 0.72));
    }
    .chart-card > * {
      position: relative;
      z-index: 1;
    }
    #pricing-visuals .chart-card {
      background-image: url('artifacts/plot_backdrop_pricing.png');
    }
    #frontier .chart-card {
      background-image: url('artifacts/plot_backdrop_frontier.png');
    }
    #pricing-visuals .chart-card::before {
      background: linear-gradient(180deg, rgba(255, 247, 238, 0.86), rgba(247, 242, 232, 0.76));
    }
    #frontier .chart-card::before {
      background: linear-gradient(180deg, rgba(247, 244, 236, 0.84), rgba(255, 248, 240, 0.70));
    }"""
    html = html.replace(marker, replacement, 1)
    html = html.replace('fill="#fffaf2"', 'fill="#fffaf2" fill-opacity="0.76"')
    return html


FIXED_REPLACEMENTS: list[tuple[str, str]] = [
    ("<html lang=\"en\">", "<html lang=\"es\">"),
    ("<title>Selvanova Competitive Report</title>", "<title>Reporte Competitivo de Selvanova</title>"),
    ("Selvanova Competitive Report", "Reporte Competitivo de Selvanova"),
    ("Selvanova Strategy File", "Expediente Estratégico de Selvanova"),
    ("Evidence quality", "Calidad de evidencia"),
    ("Revenue-grade competitive report", "Reporte competitivo orientado a ingresos"),
    ("Micro-market reverse-engineering for", "Ingeniería inversa del micromercado para"),
    ("Airbnb live extraction", "Extracción en vivo de Airbnb"),
    ("AirDNA submarket evidence", "Evidencia del submercado de AirDNA"),
    ("Executive summary", "Resumen ejecutivo"),
    ("Property snapshot", "Ficha de la propiedad"),
    ("Selvanova market overview", "Panorama del mercado Selvanova"),
    ("Direct competitors", "Competidores directos"),
    ("Aspirational competitors", "Competidores aspiracionales"),
    ("Revenue & pricing visuals", "Visuales de ingresos y precios"),
    ("Occupancy / ADR frontier", "Frontera de ocupación / ADR"),
    ("Amenity gap analysis", "Análisis de brechas de amenidades"),
    ("Review intelligence", "Inteligencia de reseñas"),
    ("Photo & copy audit", "Auditoría de fotos y copy"),
    ("Booking friction", "Fricción de reserva"),
    ("Guest segments", "Segmentos de huéspedes"),
    ("Titles & rewritten copy", "Títulos y copy reescrito"),
    ("Photo order & shot list", "Orden de fotos y lista de tomas"),
    ("Pricing recommendations", "Recomendaciones de pricing"),
    ("30/60/90 plan", "Plan 30/60/90"),
    ("Quick wins", "Victorias rápidas"),
    ("Appendix", "Apéndice"),
    ("What this report can defend", "Lo que este reporte puede sustentar"),
    ("Observed Airbnb listing attributes and search-price proxies", "Atributos observados de la ficha de Airbnb y proxies de precio observados en búsqueda"),
    ("Observed AirDNA submarket metrics for Mision de las Flores", "Métricas observadas del submercado de AirDNA para Misión de las Flores"),
    ("Explicitly labeled proxy scores where first-party revenue data is missing", "Puntajes proxy etiquetados explícitamente donde faltan datos propios de ingresos"),
    ("Artifact links", "Enlaces a artefactos"),
    ("Primary listing screenshot", "Captura de la ficha principal"),
    ("Selvanova Airbnb search screenshot", "Captura de búsqueda Airbnb Selvanova"),
    ("AirDNA submarket overview screenshot", "Captura del overview de AirDNA"),
    ("AirDNA occupancy screenshot", "Captura de ocupación de AirDNA"),
    ("AirDNA submarket snapshot JSON", "JSON del snapshot del submercado de AirDNA"),
    ("Primary Airbnb page snapshot", "Snapshot de la página principal de Airbnb"),
    ("Search HTML:", "HTML de búsqueda:"),
    ("Listing HTML:", "HTML de ficha:"),
    ("Primary listing:", "Ficha principal:"),
    ("Executive readout", "Lectura ejecutiva"),
    ("Top Selvanova winners are beating the market with trust, clarity, and practical family-group fit.", "Los ganadores top de Selvanova superan al mercado con confianza, claridad y un ajuste práctico para familias y grupos."),
    ("Your product is strong enough to compete. The monetisation gap is mostly page execution: your observed ask is premium, but your social proof is still thin and some benefits are under-sold while one visible amenity may be inaccurate.", "Tu producto es lo suficientemente fuerte para competir. La brecha de monetización está sobre todo en la ejecución de la ficha: tu precio observado es premium, pero la prueba social sigue siendo limitada y varios beneficios están subcomunicados, mientras que una amenidad visible podría ser inexacta."),
    ("Primary tension", "Tensión principal"),
    ("What top winners show", "Lo que muestran los ganadores top"),
    ("Average annual revenue across the top AirDNA 5 in this micro-market, with about 73% occupancy.", "Ingreso anual promedio entre los 5 mejores en AirDNA de este micromercado, con alrededor de 73% de ocupación."),
    ("Price Position", "Posición de precio"),
    ("PRICE POSITION", "POSICIÓN DE PRECIO"),
    ("Review Depth", "Profundidad de reseñas"),
    ("REVIEW DEPTH", "PROFUNDIDAD DE RESEÑAS"),
    ("Trust Gap", "Brecha de confianza"),
    ("TRUST GAP", "BRECHA DE CONFIANZA"),
    ("Core Strength", "Fortaleza central"),
    ("CORE STRENGTH", "FORTALEZA CENTRAL"),
    ("3BR + pools + parking", "3 recámaras + albercas + estacionamiento"),
    ("Submarket Baseline", "Base del submercado"),
    ("Observed nightly search-rate proxy vs direct Selvanova-like comps.", "Proxy observado de tarifa nocturna en búsqueda frente a comps directos tipo Selvanova."),
    ("Perfect 5.0 rating, but still early-stage social proof.", "Calificación perfecta de 5.0, pero con prueba social todavía temprana."),
    ("Main monetisation blocker relative to established nearby winners.", "Principal freno de monetización frente a ganadores cercanos ya establecidos."),
    ("The product fit is strong; the page has to communicate it faster and more credibly.", "El ajuste del producto es fuerte; la ficha tiene que comunicarlo más rápido y con más credibilidad."),
    ("Observed AirDNA overview for Mision de las Flores.", "Overview observado de AirDNA para Misión de las Flores."),
    ("Overview observado de AirDNA para Misión de las Flores.", "Vista general observada de AirDNA para Misión de las Flores."),
    ("2. Property snapshot", "2. Ficha de la propiedad"),
    ("What the listing is selling today", "Lo que está vendiendo la ficha hoy"),
    ("Observed core facts", "Hechos principales observados"),
    ("Verified host profile;", "Perfil de anfitrión verificado;"),
    ("Host verification unavailable", "Verificación de anfitrión no disponible"),
    ("response-rate blurb unavailable", "texto de tasa de respuesta no disponible"),
    ("Self check-in visible", "Llegada autónoma visible"),
    ("Self check-in weakly communicated", "Llegada autónoma comunicada débilmente"),
    ("Observed location framing:", "Enfoque de ubicación observado:"),
    ("What already works", "Lo que ya funciona"),
    ("Trust and friction snapshot", "Snapshot de confianza y fricción"),
    ("Observed nightly search-price proxy:", "Proxy observado de precio nocturno en búsqueda:"),
    ("Review themes:", "Temas de reseñas:"),
    ("Check-in/out rules:", "Reglas de check-in/out:"),
    ("Cancellation visibility:", "Visibilidad de cancelación:"),
    ("Exact public cancellation text unavailable in extracted payload", "El texto exacto público de cancelación no estuvo disponible en el payload extraído"),
    ("Fee visibility:", "Visibilidad de tarifas:"),
    ("Search results showed fee-inclusive totals; exact fee line items were not consistently exposed.", "Los resultados de búsqueda mostraron totales con tarifas incluidas; los conceptos exactos no se expusieron de forma consistente."),
    ("3 bedrooms", "3 recámaras"),
    ("4 pools", "4 albercas"),
    ("Private parking", "Estacionamiento privado"),
    ("Self check-in", "Llegada autónoma"),
    ("Workspace", "Área de trabajo"),
    ("Gym access", "Acceso al gimnasio"),
    ("Pool not visible", "Alberca no visible"),
    ("Parking unclear", "Estacionamiento poco claro"),
    ("Self check-in weak", "Llegada autónoma débil"),
    ("Workspace proof missing", "Falta prueba del área de trabajo"),
    ("Gym unclear", "Gimnasio poco claro"),
    ("3. Selvanova market overview", "3. Panorama del mercado Selvanova"),
    ("AirDNA confirms this is a practical residential base, not a beach-strip market", "AirDNA confirma que esta es una base residencial práctica, no un mercado de franja playera"),
    ("Primary submarket:", "Submercado principal:"),
    ("Mision de las Flores / Selvanova area", "Mision de las Flores / área Selvanova"),
    ("Submarket score", "Puntuación del submercado"),
    ("Rental demand 48, revenue growth 50, seasonality 90, regulation 81.", "Demanda de renta 48, crecimiento de ingresos 50, estacionalidad 90, regulación 81."),
    ("Average revenue", "Ingreso promedio"),
    ("Average ADR", "ADR promedio"),
    ("Average occupancy", "Ocupación promedio"),
    ("AirDNA guest insight summary", "Resumen de insights de huéspedes de AirDNA"),
    ("Mision de las Flores is characterized by its family-friendly atmosphere and spacious, safe residential areas. Guests often describe the neighborhood as tranquil and secure, providing a respite from the bustling tourist areas of Playa del Carmen. The proximity to supermarkets, restaurants, and local food vendors adds to the convenience, allowing visitors to feel at home while enjoying the amenities of the area. The overall vibe is relaxed, making it ideal for families and those looking for a quieter vacation experience.", "Misión de las Flores se caracteriza por su ambiente familiar y por áreas residenciales amplias y seguras. Los huéspedes suelen describir la zona como tranquila y segura, ofreciendo un respiro frente a las áreas turísticas más movidas de Playa del Carmen. La cercanía a supermercados, restaurantes y comida local suma conveniencia, permitiendo que los visitantes se sientan como en casa mientras disfrutan de las amenidades del área. El ambiente general es relajado, lo que la hace ideal para familias y para quienes buscan una experiencia de vacaciones más tranquila."),
    ("Strategic read", "Lectura estratégica"),
    ("Mision de las Flores scores 59 overall, with very high seasonality (90) and strong regulation (81), so execution quality matters more than raw market tailwind.", "Misión de las Flores puntúa 59 en total, con estacionalidad muy alta (90) y regulación fuerte (81), por lo que la calidad de ejecución importa más que el viento de cola puro del mercado."),
    ("Average submarket revenue is $194K, but top nearby 3BR listings cluster around $434K when they pair stronger trust and clearer family-group fit.", "El ingreso promedio del submercado es de $194K, pero las mejores fichas 3BR cercanas se agrupan alrededor de $434K cuando combinan más confianza y un ajuste más claro para familias y grupos."),
    ("Observed lead time is 45 days and average stay is 7 days, which supports sharper pre-arrival trust cues and practical long-stay positioning.", "El lead time observado es de 45 días y la estancia promedio es de 7 días, lo que respalda señales de confianza más nítidas antes de la llegada y un posicionamiento práctico para estancias largas."),
    ("Public AirDNA guest themes reinforce the same pattern seen on Airbnb: security, pools, family comfort, quiet, and convenience win; distance from the beach remains the main objection to neutralize.", "Los temas públicos de huéspedes en AirDNA refuerzan el mismo patrón visto en Airbnb: ganan la seguridad, las albercas, la comodidad familiar, la tranquilidad y la conveniencia; la distancia a la playa sigue siendo la principal objeción a neutralizar."),
    ("What guests love", "Lo que más gusta a los huéspedes"),
    ("Tranquil and safe residential area", "Zona residencial tranquila y segura"),
    ("Proximity to supermarkets and local eateries", "Cercanía a supermercados y comida local"),
    ("Family-friendly environment", "Entorno amigable para familias"),
    ("Well-maintained amenities and common areas", "Amenidades y áreas comunes bien mantenidas"),
    ("Easy access to nearby attractions and tourist sites", "Acceso fácil a atracciones y sitios turísticos cercanos"),
    ("Expected amenities", "Amenidades esperadas"),
    ("Swimming pools", "Albercas"),
    ("Gated communities with security", "Privadas cerradas con seguridad"),
    ("Playgrounds for children", "Áreas de juegos para niños"),
    ("BBQ areas", "Áreas de BBQ"),
    ("Fitness facilities", "Instalaciones fitness"),
    ("Common objections", "Objeciones comunes"),
    ("Distance from the beach and tourist areas", "Distancia a la playa y las zonas turísticas"),
    ("Inconsistent water pressure in some listings", "Presión de agua inconsistente en algunas propiedades"),
    ("Occasional power outages during peak times", "Cortes de energía ocasionales en horas pico"),
    ("Need for better maintenance in some properties", "Necesidad de mejor mantenimiento en algunas propiedades"),
    ("Limited public transport options", "Opciones limitadas de transporte público"),
    ("Top submarkets in Playa del Carmen", "Submercados top en Playa del Carmen"),
    ("SUBMARKET", "SUBMERCADO"),
    ("SCORE", "PUNTAJE"),
    ("Display Revenue", "Ingreso mostrado"),
    ("Display Revpar", "RevPAR mostrado"),
    ("Display Adr", "ADR mostrado"),
    ("These are AirDNA interface values as displayed on the submarket overview page.", "Estos son valores de la interfaz de AirDNA tal como se muestran en la página overview del submercado."),
    ("Top-performing Selvanova / Mision listings", "Fichas top de rendimiento en Selvanova / Misión"),
    ("TITLE", "TÍTULO"),
    ("BEDROOMS", "RECÁMARAS"),
    ("RATING", "CALIFICACIÓN"),
    ("OCCUPANCY", "OCUPACIÓN"),
    ("Accommodates", "Capacidad"),
    ("Airdna Revenue", "Ingreso AirDNA"),
    ("Airdna Adr", "ADR AirDNA"),
    ("Days Available", "Días disponibles"),
    ("These top performers are the closest evidence for the revenue frontier you are trying to join.", "Estos top performers son la evidencia más cercana de la frontera de ingresos a la que quieres entrar."),
    ("Observed AirDNA pages:", "Páginas de AirDNA observadas:"),
    ("overview screenshot", "captura overview"),
    ("occupancy screenshot", "captura de ocupación"),
    (", and the browser-observed metric snapshot saved in", "y el snapshot de métricas observado en navegador guardado en"),
    (". Source URL:", ". URL fuente:"),
    ("4. Direct competitor table", "4. Tabla de competidores directos"),
    ("Closest apartment / condo competition for the same booking mission", "Competencia más cercana de apartamentos / condos para la misma misión de reserva"),
    ("These direct comps prioritize Selvanova-like proximity, 3-bedroom family-group fit, and apartment/condo-style inventory. When strict apartment-only supply was too thin, the set widened to nearby residential equivalents and is flagged in the appendix.", "Estos comps directos priorizan cercanía tipo Selvanova, ajuste 3 recámaras para familias/grupos e inventario tipo apartamento/condo. Cuando la oferta estrictamente de departamentos fue demasiado delgada, el set se amplió a equivalentes residenciales cercanos y eso queda señalado en el apéndice."),
    ("Nightly Price Mxn", "Precio nocturno MXN"),
    ("Review Count", "Cantidad de reseñas"),
    ("Distance Km", "Distancia km"),
    ("Revenue Strength Proxy Score", "Puntaje proxy de fortaleza de ingresos"),
    ("Pricing Strength Score", "Puntaje de fortaleza de precio"),
    ("Occupancy Proxy Score", "Puntaje proxy de ocupación"),
    ("Listing Appeal Score", "Puntaje de atractivo de ficha"),
    ("Amenity Completeness Score", "Puntaje de completitud de amenidades"),
    ("Trust Review Strength Score", "Puntaje de confianza y reseñas"),
    ("Booking Friction Score", "Puntaje de fricción de reserva"),
    ("Photo Storytelling Score", "Puntaje de narrativa fotográfica"),
    ("Family Group Fit Score", "Puntaje de ajuste para familias/grupos"),
    ("Location Framing Score", "Puntaje de enfoque de ubicación"),
    ("Value For Money Score", "Puntaje de valor por dinero"),
    ("5. Aspirational competitor table", "5. Tabla de competidores aspiracionales"),
    ("Listings setting the bar for trust, clarity, and monetisation", "Fichas que marcan la vara en confianza, claridad y monetización"),
    ("Aspirational comps stay grounded in the same guest mission. They are useful because they show what stronger execution looks like without drifting into unrealistic luxury-villa inventory.", "Los comps aspiracionales se mantienen aterrizados en la misma misión del huésped. Son útiles porque muestran cómo se ve una ejecución más fuerte sin desviarse hacia inventario irreal de villas de lujo."),
    ("6. Revenue and pricing visuals", "6. Visuales de ingresos y precios"),
    ("Where the current pricing story is vulnerable", "Dónde la historia actual de pricing es vulnerable"),
    ("These plots combine observed Airbnb price points with review/trust and value scores. They are not substitutes for true host-dashboard conversion data, but they are directionally useful.", "Estas gráficas combinan puntos de precio observados en Airbnb con puntajes de reseñas/confianza y valor. No sustituyen datos reales de conversión del dashboard del anfitrión, pero sí son útiles direccionalmente."),
    ("Nightly price vs trust strength", "Precio nocturno vs fortaleza de confianza"),
    ("Observed nightly search-price proxy (MXN)", "Proxy observado de precio nocturno en búsqueda (MXN)"),
    ("Trust / review strength score", "Puntaje de confianza / reseñas"),
    ("Nightly price vs value-for-money signal", "Precio nocturno vs señal de valor por dinero"),
    ("Value-for-money score", "Puntaje de valor por dinero"),
    ("7. Occupancy / ADR frontier", "7. Frontera de ocupación / ADR"),
    ("The report’s best estimate of the revenue frontier", "La mejor estimación del reporte sobre la frontera de ingresos"),
    ("High-confidence interpretation: your listing is already priced like a stronger incumbent, but the trust stack still looks like a newer listing. That mismatch is the core frontier problem to fix.", "Interpretación de alta confianza: tu ficha ya está priceada como un incumbente más fuerte, pero el stack de confianza sigue viéndose como el de una ficha más nueva. Ese desajuste es el problema central de la frontera a resolver."),
    ("Price vs occupancy proxy", "Precio vs proxy de ocupación"),
    ("Occupancy proxy score", "Puntaje proxy de ocupación"),
    ("Revenue strength proxy ranking", "Ranking proxy de fortaleza de ingresos"),
    ("8. Amenity gap analysis", "8. Análisis de brechas de amenidades"),
    ("What matters is not just having amenities, but proving the right ones quickly", "Lo que importa no es solo tener amenidades, sino demostrar las correctas rápidamente"),
    ("Already strong", "Ya fuerte"),
    ("Under-sold or risky", "Subcomunicado o riesgoso"),
    ("Verify waterfront amenity", "Verificar amenidad tipo waterfront"),
    ("Publish Wi-Fi speed", "Publicar velocidad de Wi‑Fi"),
    ("More review depth needed", "Se necesita mayor volumen de reseñas"),
    ("Rebuild first 5 photos", "Reconstruir las primeras 5 fotos"),
    ("Lead with parking + 10 min by car", "Liderar con estacionamiento + 10 min en auto"),
    ("Must-have communication gaps", "Brechas críticas de comunicación"),
    ("Wi‑Fi speed proof and workspace proof", "Prueba de velocidad de Wi‑Fi y del área de trabajo"),
    ("Parking clarity and arrival clarity", "Claridad sobre estacionamiento y llegada"),
    ("Room-by-room sleeping fit", "Acomodo de descanso por recámara"),
    ("Earlier explanation of who this place is best for", "Explicar antes para quién es ideal este lugar"),
    ("Low-cost perceived-value upgrades", "Mejoras de valor percibido de bajo costo"),
    ("Arrival guide with parking and route guidance", "Guía de llegada con estacionamiento y ruta"),
    ("Beach towels / cooler only if real and consistently stocked", "Toallas de playa / hielera solo si son reales y siempre están disponibles"),
    ("Family convenience kit if you can operationalize it cleanly", "Kit de conveniencia familiar si puedes operacionalizarlo bien"),
    ("Wi‑Fi screenshot, workspace image, and amenity captions", "Captura de Wi‑Fi, imagen del workspace y captions de amenidades"),
    ("9. Review intelligence", "9. Inteligencia de reseñas"),
    ("What guests already reward, and what future complaints will probably be about", "Lo que los huéspedes ya premian y sobre lo que probablemente girarán las futuras quejas"),
    ("Recurring praise themes", "Temas recurrentes de elogio"),
    ("Likely complaint themes to prevent", "Temas probables de queja a prevenir"),
    ("10. Photo and listing-copy audit", "10. Auditoría de fotos y copy de la ficha"),
    ("The listing needs to sell calm, spacious group comfort in the first 10 seconds", "La ficha debe vender comodidad grupal, amplitud y calma en los primeros 10 segundos"),
    ("Observed photo story", "Narrativa fotográfica observada"),
    ("The current gallery sells", "La galería actual vende"),
    ("space and shared comfort", "amplitud y confort compartido"),
    (". Nearby winners hit a clearer emotional promise: more space, calmer nights, easier parking, and a practical family/group base.", ". Los ganadores cercanos aterrizan una promesa emocional más clara: más espacio, noches más tranquilas, estacionamiento más fácil y una base práctica para familias/grupos."),
    ("Observed first five categories: living, living, living, living, living", "Primeras cinco categorías observadas: sala, sala, sala, sala, sala"),
    ("Recommended visual promise", "Promesa visual recomendada"),
    ("Cover:", "Portada:"),
    ("bright, spacious living + terrace or living + dining frame", "sala luminosa y amplia + terraza, o encuadre sala + comedor"),
    ("First sequence:", "Primera secuencia:"),
    ("space, pool, primary bedroom, kitchen, sleeping plan, parking/security", "amplitud, alberca, recámara principal, cocina, plan de descanso, estacionamiento/seguridad"),
    ("Caption theme:", "Tema de caption:"),
    ("\"3BR for families and groups, 4 pools, private parking, self check-in, 10 min by car.\"", "\"3 recámaras para familias y grupos, 4 albercas, estacionamiento privado, llegada autónoma, a 10 min en auto.\""),
    ("11. Booking-friction audit", "11. Auditoría de fricción de reserva"),
    ("Where a guest could hesitate before pressing book", "Dónde un huésped podría dudar antes de reservar"),
    ("Primary friction callout:", "Principal alerta de fricción:"),
    ("Verify or remove the waterfront-style amenity, then make the first screen more explicit about parking, self check-in, and 10-minute-by-car access.", "Verifica o elimina la amenidad tipo waterfront, y luego haz que la primera pantalla explique mejor estacionamiento, llegada autónoma y acceso a 10 minutos en auto."),
    ("Fee friction:", "Fricción por tarifas:"),
    ("exact line-item fees were not exposed publicly, so compare your all-in total against nearby 3BR totals before trying to defend a premium.", "los conceptos exactos de tarifas no se expusieron públicamente, así que compara tu total all-in con los totales cercanos de 3 recámaras antes de intentar defender un premium."),
    ("Trust friction:", "Fricción de confianza:"),
    ("4 reviews is still light social proof for a premium-priced Selvanova option.", "4 reseñas sigue siendo poca prueba social para una opción Selvanova con precio premium."),
    ("Location friction:", "Fricción de ubicación:"),
    ("the page should say \"10 minutes by car\" early, not just later in the description.", "la ficha debe decir \"10 minutos en auto\" desde el inicio, no solo más adelante en la descripción."),
    ("Amenity friction:", "Fricción de amenidades:"),
    ("prove Wi‑Fi, parking, sleeping fit, and security visually.", "demuestra visualmente Wi‑Fi, estacionamiento, acomodo de descanso y seguridad."),
    ("12. Guest-segment playbook", "12. Playbook de segmentos de huéspedes"),
    ("Sell to the guests Selvanova naturally fits best", "Véndele a los huéspedes para quienes Selvanova encaja de forma natural"),
    ("Families", "Familias"),
    ("Positioning:", "Posicionamiento:"),
    ("Lead with 3BR layout, pools, kids club, private parking, kitchen, and sleep comfort.", "Lidera con el layout de 3 recámaras, albercas, kids club, estacionamiento privado, cocina y confort de descanso."),
    ("Objection to remove:", "Objeción a eliminar:"),
    ("Clarify that the beach is about 10 minutes by car, not walkable beachfront.", "Aclara que la playa está a unos 10 minutos en auto, no es beachfront caminable."),
    ("Must show:", "Debe mostrar:"),
    ("Beds by room, pools, terrace, dining table, parking, self check-in.", "Camas por recámara, albercas, terraza, mesa de comedor, estacionamiento y llegada autónoma."),
    ("Friend groups", "Grupos de amigos"),
    ("Sell private bedrooms plus shared living and easy rides to Quinta.", "Vende recámaras privadas más áreas comunes cómodas y trayectos fáciles a Quinta."),
    ("Remove uncertainty around parking, ride-share ease, and sleeping layout.", "Elimina la incertidumbre sobre estacionamiento, facilidad de rideshare y distribución para dormir."),
    ("Living room, bedroom separation, pool, outdoor dining, smart TV.", "Sala, separación entre recámaras, alberca, comedor exterior y smart TV."),
    ("Longer stays", "Estancias largas"),
    ("Promote kitchen, laundry, workspace, AC, calm residential setting, nearby shopping.", "Promociona cocina, lavandería, área de trabajo, A/C, entorno residencial tranquilo y comercios cercanos."),
    ("Publish Wi-Fi speed and remote-work-ready surface.", "Publica la velocidad del Wi‑Fi y una superficie lista para trabajo remoto."),
    ("Workspace, Wi-Fi speed screenshot, washer/dryer, kitchen storage, parking.", "Workspace, captura de velocidad Wi‑Fi, lavadora/secadora, almacenamiento en cocina y estacionamiento."),
    ("Park and mobility travelers", "Viajeros de parques y movilidad"),
    ("Frame the unit as a practical launchpad for beach days, parks, cenotes, and town nights.", "Enmarca la unidad como una base práctica para días de playa, parques, cenotes y salidas por la ciudad."),
    ("Be explicit that a car or rideshare is the easiest fit.", "Sé explícito en que auto o rideshare es la forma más fácil de moverse."),
    ("Parking, self check-in, calm arrival, practical location copy.", "Estacionamiento, llegada autónoma, arribo tranquilo y copy de ubicación práctico."),
    ("Value-seeking space buyers", "Compradores de espacio orientados al valor"),
    ("Compare implicitly against paying for multiple hotel rooms or a cramped 2BR.", "Compáralo implícitamente contra pagar varias habitaciones de hotel o un 2BR apretado."),
    ("Demonstrate why the inland location is worth the trade for space and amenities.", "Demuestra por qué la ubicación tierra adentro vale la pena a cambio de espacio y amenidades."),
    ("Square-meter feel, terrace, bed plan, pools, family amenities.", "Sensación de metros cuadrados, terraza, plan de camas, albercas y amenidades familiares."),
    ("13. Recommended listing titles and rewritten copy", "13. Títulos recomendados y copy reescrito"),
    ("Lead with fit, not generic luxury language", "Lidera con el ajuste del huésped, no con lenguaje genérico de lujo"),
    ("Title options", "Opciones de título"),
    ("Selvanova 3BR for Families | Pools, parking, 10 min beach", "Selvanova 3 recámaras para familias | Albercas, estacionamiento, playa a 10 min"),
    ("Spacious Selvanova 3BR | 4 pools, gym, private parking", "Amplio 3 recámaras en Selvanova | 4 albercas, gimnasio, estacionamiento privado"),
    ("Quiet 3BR in Selvanova | Family-ready, self check-in", "Tranquilo 3 recámaras en Selvanova | Ideal para familias, llegada autónoma"),
    ("3BR Playa base in Selvanova | Pools, AC, parking", "Base 3 recámaras en Playa desde Selvanova | Albercas, A/C, estacionamiento"),
    ("Family condo in Selvanova | 3BR, terrace, 10 min beach", "Condo familiar en Selvanova | 3 recámaras, terraza, playa a 10 min"),
    ("Selvanova 3BR retreat | 4 pools, kids club, parking", "Refugio 3 recámaras en Selvanova | 4 albercas, kids club, estacionamiento"),
    ("Spacious Playa del Carmen 3BR | Selvanova, pools, gym", "Amplio 3 recámaras en Playa del Carmen | Selvanova, albercas, gym"),
    ("Secure Selvanova 3BR | Terrace, pools, easy beach access", "3 recámaras seguro en Selvanova | Terraza, albercas, acceso fácil a la playa"),
    ("3BR for groups in Selvanova | Parking, pools, AC", "3 recámaras para grupos en Selvanova | Estacionamiento, albercas, A/C"),
    ("Quiet family stay in Selvanova | 3BR, pools, 5th Ave by car", "Estancia familiar tranquila en Selvanova | 3 recámaras, albercas, 5ta en auto"),
    ("What guests should understand in 10 seconds", "Lo que el huésped debe entender en 10 segundos"),
    ("3 bedrooms, 2 baths, up to 6 guests: clear fit for families and friend groups.", "3 recámaras, 2 baños, hasta 6 huéspedes: ajuste claro para familias y grupos de amigos."),
    ("Quiet Selvanova residential setting with 4 pools, gym, kids club, BBQ areas, and private parking.", "Entorno residencial tranquilo en Selvanova con 4 albercas, gimnasio, kids club, áreas de BBQ y estacionamiento privado."),
    ("10 minutes by car to the beach and Quinta Avenida: honest location framing, not a beach-strip promise.", "10 minutos en auto a la playa y Quinta Avenida: enfoque honesto de ubicación, no una promesa de franja playera."),
    ("Self check-in, full kitchen, laundry, AC in every bedroom, and large TV room reduce booking anxiety fast.", "Llegada autónoma, cocina completa, lavandería, A/C en cada recámara y una sala grande de TV reducen rápido la ansiedad de reserva."),
    ("Best for guests who want more space, calmer nights, and easier logistics than a compact downtown condo.", "Ideal para huéspedes que quieren más espacio, noches más tranquilas y logística más fácil que en un condo compacto del centro."),
    ("Family-first", "Primero familias"),
    ("Friends and group stays", "Amigos y grupos"),
    ("Long-stay and practical base", "Base práctica para estancias largas"),
    ("<strong>EN:</strong>", "<strong>Inglés:</strong>"),
    ("<strong>ES:</strong>", "<strong>Español:</strong>"),
    ("14. Recommended photo order and missing shots", "14. Orden recomendado de fotos y tomas faltantes"),
    ("Build the click and the conversion in the same sequence", "Construye el clic y la conversión en la misma secuencia"),
    ("Bright living room plus terrace hero shot with the apartment feeling open, not cropped.", "Hero shot de sala luminosa más terraza, con el departamento sintiéndose abierto y no recortado."),
    ("One clean pool lifestyle image that feels family-ready, not just generic amenities.", "Una imagen limpia de estilo de vida en alberca que se sienta lista para familias, no solo amenidades genéricas."),
    ("Primary bedroom with bed size and natural light clearly visible.", "Recámara principal con el tamaño de cama y la luz natural claramente visibles."),
    ("Second and third bedroom shots that prove the group sleeping plan immediately.", "Tomas de la segunda y tercera recámara que prueben de inmediato el plan de descanso del grupo."),
    ("Kitchen plus dining setup ready for a real meal, not a detail close-up.", "Cocina más montaje de comedor listo para una comida real, no un acercamiento de detalle."),
    ("Private parking and controlled-access entry shot to reduce mobility and safety anxiety.", "Toma de estacionamiento privado y acceso controlado para reducir ansiedad por movilidad y seguridad."),
    ("Workspace/Wi-Fi proof image, ideally with a speed-test screen.", "Imagen que pruebe workspace/Wi‑Fi, idealmente con pantalla de speed test."),
    ("A practical local-context image or caption card: 10 min by car to beach and Quinta, shopping nearby.", "Una imagen de contexto local o card de caption práctica: playa y Quinta a 10 min en auto, compras cerca."),
    ("15. Pricing / minimum-night / fee / cancellation recommendations", "15. Recomendaciones de pricing / estancia mínima / tarifas / cancelación"),
    ("Monetise like a strong incumbent only after earning incumbent-level trust", "Monetiza como un incumbente fuerte solo después de ganar confianza al nivel de un incumbente"),
    ("Hold a premium only when trust improves:", "Sostén un premium solo cuando mejore la confianza:"),
    ("Observed 2-night search pricing puts the listing about 58.9% above the direct-comp median. With only 4 reviews, premium pricing needs stronger photo and trust proof than higher-social-proof Selvanova rivals.", "El precio observado en búsqueda para 2 noches coloca la ficha aproximadamente 58.9% por encima de la mediana directa. Con solo 4 reseñas, el pricing premium necesita una prueba fotográfica y de confianza más fuerte que la de rivales Selvanova con mayor prueba social."),
    ("ADR and conversion.", "ADR y conversión."),
    ("Test a lower weekend entry point until review count reaches double digits:", "Prueba un precio de entrada de fin de semana más bajo hasta que el volumen de reseñas llegue a doble dígito:"),
    ("A slightly more compelling first-booking price can reduce review-count drag and accelerate ranking-safe social proof.", "Un precio de primera reserva un poco más atractivo puede reducir el lastre del volumen de reseñas y acelerar una prueba social segura para ranking."),
    ("Occupancy, ranking, reviews.", "Ocupación, ranking, reseñas."),
    ("Audit fee load inside the host dashboard:", "Audita la carga de tarifas dentro del dashboard del anfitrión:"),
    ("Search results show fee-inclusive totals, but exact fee lines were not exposed in the listing payload. If the all-in total feels high versus nearby 3BRs, conversion will suffer before guests even click.", "Los resultados de búsqueda muestran totales con tarifas incluidas, pero los conceptos exactos no se expusieron en el payload de la ficha. Si el total all-in se siente alto frente a 3BRs cercanos, la conversión sufrirá antes de que el huésped siquiera haga clic."),
    ("Conversion and occupancy.", "Conversión y ocupación."),
    ("Keep self check-in and clarify it visually:", "Mantén la llegada autónoma y aclárala visualmente:"),
    ("This is already a conversion asset. It reduces arrival friction and matters more in a car-based residential location.", "Esto ya es un activo de conversión. Reduce la fricción de llegada y pesa más en una ubicación residencial basada en auto."),
    ("Conversion, reviews.", "Conversión, reseñas."),
    ("Review cancellation setting for competitiveness:", "Revisa la configuración de cancelación para competitividad:"),
    ("Exact cancellation terms were not exposed publicly here. If your setting is stricter than nearby family-group comps, a more flexible option can help a low-review listing compete.", "Los términos exactos de cancelación no se expusieron públicamente aquí. Si tu configuración es más estricta que la de comps cercanos para familias/grupos, una opción más flexible puede ayudar a competir a una ficha con pocas reseñas."),
    ("Conversion and ranking competitiveness.", "Conversión y competitividad de ranking."),
    ("16. 30/60/90 day action plan", "16. Plan de acción 30/60/90 días"),
    ("What to do now, next, and after the next review wave lands", "Qué hacer ahora, después y tras la próxima ola de reseñas"),
    ("Window", "Ventana"),
    ("What to change", "Qué cambiar"),
    ("Why it matters", "Por qué importa"),
    ("Evidence", "Evidencia"),
    ("Impact", "Impacto"),
    ("Confidence", "Confianza"),
    ("Difficulty", "Dificultad"),
    ("0-7 days", "0-7 días"),
    ("8-30 days", "8-30 días"),
    ("31-90 days", "31-90 días"),
    ("Verify and remove any inaccurate amenity, especially 'Frente al agua', if it is not literally true.", "Verifica y elimina cualquier amenidad inexacta, especialmente 'Frente al agua', si no es literalmente cierta."),
    ("An inland Selvanova apartment should not risk guest disappointment with a waterfront-type amenity signal.", "Un departamento Selvanova tierra adentro no debería arriesgar decepción del huésped con una señal de amenidad tipo waterfront."),
    ("Observed on the public Airbnb amenity list.", "Observado en la lista pública de amenidades de Airbnb."),
    ("Reviews, conversion, policy safety", "Reseñas, conversión, seguridad de cumplimiento"),
    ("Replace the headline and first-screen copy with a fit-led version: 3BR, pools, parking, self check-in, 10 min by car.", "Reemplaza el headline y el copy de primera pantalla con una versión guiada por ajuste: 3 recámaras, albercas, estacionamiento, llegada autónoma, 10 min en auto."),
    ("Current title is more generic and less trust-building than the best Selvanova messaging patterns.", "El título actual es más genérico y construye menos confianza que los mejores patrones de mensajería de Selvanova."),
    ("Observed title plus nearby comp positioning.", "Título observado más posicionamiento de comps cercanos."),
    ("Conversion", "Conversión"),
    ("Reorder the first 8 photos to show space, pool, primary bedroom, kitchen, second/third bedroom, parking/security, terrace, lifestyle.", "Reordena las primeras 8 fotos para mostrar amplitud, alberca, recámara principal, cocina, segunda/tercera recámara, estacionamiento/seguridad, terraza y lifestyle."),
    ("The apartment needs to win the 'will my group fit comfortably?' decision in seconds.", "El departamento necesita ganar en segundos la decisión de '¿mi grupo cabrá cómodamente?'."),
    ("Photo-order patterns and search-result hero signals.", "Patrones de orden fotográfico y señales hero en resultados de búsqueda."),
    ("Conversion, CTR", "Conversión, CTR"),
    ("Add Wi-Fi speed proof and workspace proof to the gallery and description.", "Agrega prueba de velocidad de Wi‑Fi y prueba de workspace a la galería y a la descripción."),
    ("Selvanova also competes for longer stays and remote/hybrid travelers. Right now the Wi-Fi benefit is underspecified.", "Selvanova también compite por estancias largas y viajeros remotos/híbridos. Ahora mismo el beneficio del Wi‑Fi está subespecificado."),
    ("Workspace amenity is present; speed proof is not visible.", "La amenidad de workspace está presente; la prueba de velocidad no es visible."),
    ("Occupancy, conversion", "Ocupación, conversión"),
    ("Push for the next 8-12 high-quality reviews with a tighter arrival guide, local guidebook, and post-stay feedback loop.", "Empuja las próximas 8-12 reseñas de alta calidad con una guía de llegada más cerrada, guía local y un ciclo de feedback post-estancia."),
    ("Search pricing is roughly 58.9% above the direct-comp median.", "El pricing observado en búsqueda está aproximadamente 58.9% por encima de la mediana directa."),
    ("4 reviews versus stronger Selvanova rivals with far deeper social proof.", "4 reseñas frente a rivales Selvanova más fuertes y con mucha más prueba social."),
    ("Conversion, ranking, ADR", "Conversión, ranking, ADR"),
    ("Tune the price ladder to earn more clicks before raising back to premium.", "Ajusta la escalera de precios para ganar más clics antes de volver a subir a premium."),
    ("A newer listing can monetise more effectively by trading a small amount of ADR for review momentum and occupancy proof.", "Una ficha más nueva puede monetizar mejor intercambiando una pequeña porción de ADR por momentum de reseñas y prueba de ocupación."),
    ("Observed direct-comp price and review spread.", "Spread observado de precio y reseñas en comps directos."),
    ("Occupancy, reviews, ranking", "Ocupación, reseñas, ranking"),
    ("Build a family-ready trust stack: crib/high chair only if real, beach towels/cooler, kitchen starter kit, arrival video.", "Construye un stack de confianza listo para familias: cuna/silla alta solo si son reales, toallas de playa/hielera, kit inicial de cocina y video de llegada."),
    ("This listing naturally fits families and groups. Small operational touches create the next wave of review tags.", "Esta ficha encaja naturalmente con familias y grupos. Pequeños toques operativos crean la siguiente ola de tags en reseñas."),
    ("Review tags already lean toward hospitality, comfort, family, sleep, and amenities.", "Los tags de reseñas ya se inclinan hacia hospitalidad, comodidad, familia, descanso y amenidades."),
    ("Reviews, conversion", "Reseñas, conversión"),
    ("A/B test cover-photo concepts between interior-space hero and pool-lifestyle hero.", "Haz A/B test de conceptos de foto de portada entre hero de espacio interior y hero de estilo de vida con alberca."),
    ("The winning image should improve click-through rate in search without discounting.", "La imagen ganadora debería mejorar el CTR en búsqueda sin descontar."),
    ("Observed competitive cover-photo patterns and the listing's current premium position.", "Patrones observados de fotos de portada competitivas y la posición premium actual de la ficha."),
    ("CTR, conversion, ranking", "CTR, conversión, ranking"),
    ("Strengthen authority cues around hosting consistency: guidebook polish, repeated review themes, cohost responsiveness, and cleaner operational scripts.", "Fortalece señales de autoridad alrededor de la consistencia del hosting: guía del huésped más pulida, temas de reseña repetidos, capacidad de respuesta del cohost y guiones operativos más limpios."),
    ("Trust is the main gap versus established Selvanova winners, not raw amenity count.", "La confianza es la principal brecha frente a ganadores establecidos de Selvanova, no el conteo bruto de amenidades."),
    ("Observed host age/review count gap versus aspirational comps.", "Brecha observada de antigüedad del anfitrión / volumen de reseñas frente a comps aspiracionales."),
    ("Reviews, ADR, conversion", "Reseñas, ADR, conversión"),
    ("Re-check cancellation, minimum-night, and fee settings against live competitors inside the host dashboard.", "Revisa otra vez cancelación, estancia mínima y tarifas frente a competidores vivos dentro del dashboard del anfitrión."),
    ("AirDNA metrics and exact public cancellation text were blocked, so the final monetisation edge must be tuned with dashboard-side settings.", "Las métricas de AirDNA y el texto exacto público de cancelación estuvieron bloqueados, así que el ajuste final de monetización debe afinarse con la configuración dentro del dashboard."),
    ("Public extraction gap plus search-result total-price spread.", "Brecha de extracción pública más spread de precio total en resultados de búsqueda."),
    ("Conversion, occupancy, ADR", "Conversión, ocupación, ADR"),
    ("17. High-confidence quick wins", "17. Victorias rápidas de alta confianza"),
    ("No-regret changes that should improve conversion quality fast", "Cambios sin arrepentimiento que deberían mejorar rápido la calidad de conversión"),
    ("Verify the 'Frente al agua' amenity immediately; remove it if inaccurate.", "Verifica de inmediato la amenidad 'Frente al agua'; elimínala si es inexacta."),
    ("Change the title from generic luxury language to fit-led Selvanova positioning.", "Cambia el título de lenguaje genérico de lujo a un posicionamiento Selvanova guiado por ajuste."),
    ("Move pool, living room, and bedroom proof into the first 5 photos.", "Mueve prueba de alberca, sala y recámaras a las primeras 5 fotos."),
    ("Publish a Wi-Fi speed screenshot and workspace photo.", "Publica una captura de velocidad Wi‑Fi y una foto del workspace."),
    ("State '10 minutes by car to the beach and Quinta' exactly and early.", "Declara '10 minutos en auto a la playa y a Quinta' de forma exacta y desde el inicio."),
    ("Lead with private parking and self check-in in the first screen.", "Lidera con estacionamiento privado y llegada autónoma en la primera pantalla."),
    ("Add room-by-room bed labels to captions or description.", "Agrega etiquetas de camas por recámara en captions o descripción."),
    ("Use review themes like comfort, hospitality, family, and sleep in copy without copying guest text.", "Usa temas de reseñas como comodidad, hospitalidad, familia y descanso en el copy sin copiar texto de huéspedes."),
    ("Sharpen family/group positioning instead of trying to sound beachfront.", "Afila el posicionamiento familiar/grupal en lugar de intentar sonar beachfront."),
    ("Audit fee load and weekend entry pricing before pushing ADR higher.", "Audita la carga de tarifas y el precio de entrada de fin de semana antes de empujar el ADR al alza."),
    ("18. Appendix with raw data, assumptions, and data-quality notes", "18. Apéndice con datos brutos, supuestos y notas de calidad de datos"),
    ("What was observed directly, what was inferred, and what remained blocked", "Qué se observó directamente, qué se infirió y qué quedó bloqueado"),
    ("Blocked or unavailable fields", "Campos bloqueados o no disponibles"),
    ("AirDNA submarket overview pages were accessible, but the listing-specific AirDNA page and raw API response bodies were not exported directly from the browser session.", "Las páginas overview del submercado en AirDNA fueron accesibles, pero la página específica de la ficha y los cuerpos crudos de respuesta API no se exportaron directamente desde la sesión del navegador."),
    ("Some AirDNA panels show abbreviated currency displays; values are cited as observed from the interface rather than treated as fully normalized exports unless otherwise noted.", "Algunos paneles de AirDNA muestran monedas abreviadas; los valores se citan tal como se observaron en la interfaz y no se tratan como exportaciones totalmente normalizadas salvo que se indique lo contrario."),
    ("Exact Airbnb cancellation-policy text was not exposed in the public listing payload.", "El texto exacto de la política de cancelación de Airbnb no se expuso en el payload público de la ficha."),
    ("Exact cleaning-fee and tax line items were not consistently exposed on public listing pages; search results showed fee-inclusive totals only.", "Los conceptos exactos de limpieza e impuestos no se expusieron de forma consistente en páginas públicas de fichas; los resultados de búsqueda solo mostraron totales con tarifas incluidas."),
    ("Public review payloads exposed review tags and category ratings more reliably than full review text.", "Los payloads públicos de reseñas expusieron los tags de reseñas y las calificaciones por categoría con más fiabilidad que el texto completo de las reseñas."),
    ("No host-dashboard-only signals were available: impression share, click-through rate, conversion rate, or booking lead-time data.", "No hubo señales exclusivas del dashboard del anfitrión disponibles: impression share, click-through rate, conversion rate ni datos de lead time de reserva."),
    ("Observed artifacts", "Artefactos observados"),
    ("Structured outputs:", "Outputs estructurados:"),
    ("AirDNA submarket observations are saved in", "Las observaciones del submercado de AirDNA se guardan en"),
]


REGEX_REPLACEMENTS: list[tuple[str, str | re.Pattern[str] | callable]] = [
    (r"AirDNA submarket: ([0-9.]+) score", r"Submercado de AirDNA: \1 puntos"),
    (r"Generated ([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:]+ [A-Z]+)", r"Generado \1"),
    (r"Observed nightly search-price proxy with only (\d+) reviews\.", r"Proxy observado de precio nocturno en búsqueda con solo \1 reseñas."),
    (r"(\d+) reviews below direct median", r"\1 reseñas por debajo de la mediana directa"),
    (r"(\d+(?:\.\d+)?) guests, (\d+(?:\.\d+)?) bedrooms, (\d+(?:\.\d+)?) beds, (\d+(?:\.\d+)?) baths", r"\1 huéspedes, \2 recámaras, \3 camas, \4 baños"),
    (r"(\d+(?:\.\d+)?) rating from (\d+) reviews", r"Calificación \1 con \2 reseñas"),
    (r"([A-Za-zÁÉÍÓÚáéíóúÑñüÜ /]+): mentioned by (\d+) review\(s\)", lambda m: f"{m.group(1)}: aparece en {m.group(2)} reseña(s)"),
    (r"(-?\d+(?:\.\d+)?%) past year", r"\1 último año"),
]


def translate(html: str) -> str:
    html = inject_chart_styling(html)
    for old, new in sorted(FIXED_REPLACEMENTS, key=lambda item: len(item[0]), reverse=True):
        html = html.replace(old, new)
    for pattern, repl in REGEX_REPLACEMENTS:
        html = re.sub(pattern, repl, html)

    html = re.sub(r">\s*High\s*<", ">Alta<", html)
    html = re.sub(r">\s*Medium\s*<", ">Media<", html)
    html = re.sub(r">\s*Low\s*<", ">Baja<", html)
    html = html.replace(">Title<", ">Título<")
    html = html.replace(">Bedrooms<", ">Recámaras<")
    html = html.replace(">Rating<", ">Calificación<")
    html = html.replace(">Occupancy<", ">Ocupación<")
    html = html.replace(">Guests<", ">Huéspedes<")
    html = html.replace(">Beds<", ">Camas<")
    html = html.replace(">Submarket<", ">Submercado<")
    html = html.replace(">Score<", ">Puntaje<")
    html = html.replace("4 reviews", "4 reseñas")
    html = html.replace("active listings", "anuncios activos")
    html = html.replace("across 414 anuncios activos", "sobre 414 anuncios activos")
    html = html.replace("Overview observado de AirDNA para Misión de las Flores.", "Vista general observada de AirDNA para Misión de las Flores.")
    html = html.replace("captura overview", "captura del overview")
    html = html.replace("58.9% vs direct median", "58.9% vs mediana directa")
    html = html.replace("54% occ. / $1.0K ADR", "54% ocup. / $1.0K ADR")
    return html


def main() -> None:
    html = SOURCE_HTML.read_text(encoding="utf-8")
    translated = translate(html)
    TARGET_HTML.write_text(translated, encoding="utf-8")
    print(TARGET_HTML)


if __name__ == "__main__":
    main()
