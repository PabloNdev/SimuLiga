import Link from "next/link";
import { ValidationPanel } from "@/components/ValidationPanel";

export const metadata = {
  title: "Método · SimuLiga",
  description:
    "Cómo SimuLiga combina Elo, Davidson y simulaciones de Montecarlo para proyectar LaLiga.",
};

export default function MethodologyPage() {
  return (
    <div className="container">
      <div className="page-head">
        <div>
          <span className="kicker">Metodología</span>
          <h1 className="page-title">
            Cómo se calcula <em>todo</em>.
          </h1>
          <p className="page-sub">
            Sin cajas negras: qué datos entran, qué modelo transforma fuerzas en
            probabilidades y cómo se resuelve una temporada simulada.
          </p>
        </div>
        <div className="page-actions">
          <Link href="/" className="btn">
            Volver al panel
          </Link>
          <Link href="/escenario" className="btn btn-primary">
            Probar escenario
          </Link>
        </div>
      </div>

      <div className="method">
        <ValidationPanel />

        <div className="method-grid">
          <section className="panel method-card">
            <h2>1 · Datos y fuerza</h2>
            <p>
              Cada temporada cargada tiene 20 equipos y 380 partidos. Los resultados ya
              jugados se conservan; los pendientes se simulan. Cada equipo
              arranca con un Elo de referencia y lo actualiza tras cada partido
              con la fórmula clásica de Elo, ajustada por margen de goles.
            </p>
            <h3>Expectativa de victoria</h3>
            <pre className="formula">{`E_local = 1 / (1 + 10^(-(Elo_local + ventaja - Elo_visitante)/400))`}</pre>
            <h3>Actualización</h3>
            <pre className="formula">{`Elo_nuevo = Elo + K · multiplicador_margen · (resultado − E)`}</pre>
            <p>
              El resultado vale 1 (victoria), 0,5 (empate) o 0 (derrota). El
              margen de goles amplifica el cambio en victorias amplias. Los
              ratings se reconstruyen con los resultados reales de 2020–2024 y
              se actualizan con las jornadas ya disputadas de la temporada
              cargada. La temporada 2025/26 se reaplica completa: 380 partidos,
              incluidos los de los equipos que ya no están en LaLiga. Los equipos
              que no jugaron la temporada anterior entran con la media de los tres
              descendidos, no con 1500.
            </p>
            <div className="page-actions">
              <Link href="/elo" className="link-arrow">
                Ver el ELO de cada equipo y su evolución
              </Link>
            </div>
          </section>

          <section className="panel method-card">
            <h2>2 · Probabilidad 1X2</h2>
            <p>
              El modelo Davidson convierte la diferencia de Elo en tres
              probabilidades. El parámetro <code>H</code> recoge la ventaja de
              jugar en casa; <code>ν</code> regula la frecuencia de empates.
            </p>
            <pre className="formula">{`r = 10^((ΔElo + H) / 400)

P(local) = r / (r + 1 + ν√r)
P(empate) = ν√r / (r + 1 + ν√r)
P(visitante) = 1 / (r + 1 + ν√r)`}</pre>
            <p>
              Las tres probabilidades suman 1. SimuLiga simula cada partido
              pendiente muestreando uno de estos tres resultados 1X2 (victoria
              local, empate o victoria visitante).
            </p>
          </section>

          <section className="panel method-card">
            <h2>3 · Simulación de Montecarlo</h2>
            <p>
              Cada temporada simulada juega los 380 partidos: conserva los
              resultados reales y resuelve los pendientes. Se asignan 3 puntos
              por victoria y 1 por empate, se ordena la tabla con las reglas de
              LaLiga y se guarda la posición final de cada equipo.
            </p>
            <p>
              Repitiendo el proceso miles de veces se estima la probabilidad de
              cada evento:
            </p>
            <pre className="formula">{`P(campeón) = temporadas con posición 1 / total de simulaciones

P(Top 4) = temporadas entre los 4 primeros / total
P(descenso) = temporadas en los 3 últimos / total`}</pre>
            <p>
              El panel usa 10.000 simulaciones para responder rápido y permite
              lanzar 1.000.000 para una estimación final. Las simulaciones
              rápidas pueden variar unas décimas; la estructura de la tabla no
              debería cambiar.
            </p>
          </section>
        </div>

        <section className="panel method-card">
          <h2>4 · Desempates de LaLiga</h2>
          <p>
            Cuando dos o más equipos terminan con los mismos puntos, el orden no
            es la diferencia de goles global: primero manda el duelo directo.
            SimuLiga aplica esta secuencia.
          </p>
          <ol className="rules-list">
            <li>Mayor número de puntos en los partidos entre los equipos empatados.</li>
            <li>Mayor diferencia de goles en esos partidos entre sí.</li>
            <li>Mayor número de goles marcados en esos partidos entre sí.</li>
            <li>Mayor diferencia de goles en la clasificación general.</li>
            <li>Mayor número de goles marcados en la clasificación general.</li>
            <li>Menor puntuación de fair play.</li>
            <li>Sorteo si persiste el empate.</li>
          </ol>
          <p style={{ marginTop: 14 }}>
            Los criterios de duelo directo solo se aplican cuando todos los
            partidos entre los equipos implicados se han disputado. Como los
            partidos simulados solo producen resultados 1X2 (sin goles
            simulados), los desempates usan los puntos del duelo directo
            (conservando los goles reales ya jugados) y un sorteo neutral si
            persiste el empate.
          </p>
          <div className="method-note">
            El sorteo final se implementa con una clave aleatoria por simulación.
            Es una aproximación neutral: reparte los empates imposibles de
            resolver con los criterios anteriores sin favorecer a ningún equipo.
          </div>
        </section>

        <div className="method-grid">
          <section className="panel method-card">
            <h2>5 · Datos y actualización</h2>
            <p>
              La app lee calendario y resultados reales de OpenFootball y
              football-data.co.uk. La clave de API-Football solo es necesaria para
              el modo alternativo. El histórico cubre 2020–2024 y ahora mismo el
              panel carga 2026/27 con las jornadas ya disputadas. Sin fuente real
              se usa un snapshot de demostración.
            </p>
            <p>
              Los ratings se reconstruyen con el histórico 2020–2024 (cinco
              temporadas), se reaplican con 2025/26 y se actualizan con las
              jornadas disputadas de 2026/27. Cada proyección guarda la versión de
              datos, el modo y la semilla, de modo que el mismo escenario se puede
              reproducir.
            </p>
            <div className="method-note">
              El histórico se usa para calibrar <code>H</code> y <code>ν</code> por
              máxima verosimilitud, con validación temporal sobre 2024/25. El panel
              superior muestra accuracy, log-loss y Brier. El análisis de
              calibración de los ratings de inicio está documentado en{" "}
              <code>docs/elo-calibration-2026.md</code>.
            </div>
          </section>

          <section className="panel method-card">
            <h2>6 · Qué no es</h2>
            <p>
              No es una promesa ni una recomendación de apuestas. Es un modelo
              condicionado a los datos y supuestos actuales. Cambiar un rating,
              una lesión o un resultado mueve las probabilidades; eso es
              precisamente lo que hace útil el laboratorio.
            </p>
            <ul>
              <li>Las probabilidades no incorporan lesiones, sanciones ni mercado.</li>
              <li>Si no hay clave, la demo usa datos generados; no son resultados reales.</li>
              <li>El sorteo final solo actúa cuando todos los criterios empatan.</li>
            </ul>
            <p>
              Para leer bien el panel: empieza por la probabilidad de campeón,
              después mira el rango de puntos y, si te interesa un equipo, abre
              su distribución. La incertidumbre también es información.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
