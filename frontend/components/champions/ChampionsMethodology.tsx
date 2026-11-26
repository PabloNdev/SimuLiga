import Link from "next/link";

export function ChampionsMethodology() {
  return (
    <div className="container">
      <div className="page-head">
        <div>
          <span className="kicker">Metodología · SimuChampions</span>
          <h1 className="page-title">
            Cómo se calcula <em>todo</em>.
          </h1>
          <p className="page-sub">
            Sin cajas negras: qué datos entran, cómo se reconstruye el ELO, cómo
            se convierte en probabilidades y cómo se resuelve una Champions
            simulada.
          </p>
        </div>
        <div className="page-actions">
          <Link href="/champions" className="btn">
            Volver al panel
          </Link>
          <Link href="/champions/playoff" className="btn btn-primary">
            Ver playoff
          </Link>
        </div>
      </div>

      <div className="method">
        <div className="method-grid">
          <section className="panel method-card">
            <h2>1 · Formato</h2>
            <p>
              La Champions 2024/25 estrenó una fase de liga única de 36 equipos.
              Cada equipo juega 8 partidos, 4 en casa y 4 fuera, contra 8 rivales
              distintos. No hay ida y vuelta en la fase de liga.
            </p>
            <p>
              Los puestos 1-8 pasan directamente a octavos. Los puestos 9-24
              juegan un playoff a dos partidos. Los puestos 25-36 quedan
              eliminados.
            </p>
            <pre className="formula">{`1-8   → octavos
9-24  → playoff (ida y vuelta)
25-36 → eliminado`}</pre>
          </section>

          <section className="panel method-card">
            <h2>2 · Datos</h2>
            <p>
              La fuente principal es API-Football. Si no está disponible, se usa
              OpenFootball <code>cl.txt</code>. Después se recurre a la caché y,
              por último, a un modo demo etiquetado.
            </p>
            <p>
              La temporada 2025/26 se usa para reconstruir el ELO y calibrar el
              modelo. La 2026/27 es la vista activa. Si aún no está publicada, la
              app muestra 2025/26 con las primeras jornadas reales y el resto
              simulado, y lo indica en la cabecera.
            </p>
            <div className="method-note">
              La app nunca presenta datos simulados como reales: el campo{" "}
              <code>data_note</code> y el aviso de la cabecera lo indican.
            </div>
          </section>
        </div>

        <div className="method-grid">
          <section className="panel method-card">
            <h2>3 · ELO</h2>
            <p>
              Cada equipo arranca con su ELO de ClubElo al inicio de 2025/26. Si
              ClubElo no está disponible, todos parten de 1500 y la verificación
              lo indica con <code>seed_source = &quot;fallback_1500&quot;</code>.
            </p>
            <pre className="formula">{`E_local = 1 / (1 + 10^(-((Elo_local + H) - Elo_visitante)/400))

ΔElo = K × multiplicador_margen × (resultado − E_local)`}</pre>
            <p>
              Se reaplican los 189 partidos de 2025/26 en orden cronológico:
              fase de liga, playoff, octavos, cuartos, semifinales y final. El
              resultado usado es el de 90 minutos. La final se trata como sede
              neutral.
            </p>
            <p>
              Los equipos nuevos de 2026/27 parten del ClubElo de 2026 o de la
              media de los nuevos. Después se aplican los partidos ya jugados.
            </p>
          </section>

          <section className="panel method-card">
            <h2>4 · Probabilidad 1X2</h2>
            <p>
              El modelo Davidson convierte la diferencia de ELO en tres
              probabilidades. <code>H</code> recoge la ventaja de casa y{" "}
              <code>nu</code> la frecuencia de empates.
            </p>
            <pre className="formula">{`r = 10^((ΔElo + H) / 400)

P(local)     = r / (r + 1 + nu·√r)
P(empate)    = nu·√r / (r + 1 + nu·√r)
P(visitante) = 1 / (r + 1 + nu·√r)`}</pre>
            <p>
              Los parámetros se ajustan con la Champions 2025/26: jornadas 1-6
              para entrenar, 7-8 y eliminatorias para validar, y toda la
              temporada para el ajuste final. Si falla, se usan los de LaLiga
              como respaldo.
            </p>
          </section>
        </div>

        <div className="method-grid">
          <section className="panel method-card">
            <h2>5 · Simulación</h2>
            <p>
              Cada simulación conserva los partidos reales y juega los
              pendientes en formato 1X2 (sin goles simulados). Se construye la
              tabla de 36 conservando los goles reales ya disputados y
              resolviendo los desempates por puntos, victorias y sorteo
              determinista.
            </p>
            <ol className="rules-list">
              <li>Puntos.</li>
              <li>Diferencia de goles.</li>
              <li>Goles a favor.</li>
              <li>Goles como visitante.</li>
              <li>Victorias.</li>
              <li>Victorias como visitante.</li>
              <li>Sorteo determinista si persiste el empate.</li>
            </ol>
            <p>
              No se modelan puntos de disciplina ni coeficiente UEFA: el sorteo
              cubre el último criterio.
            </p>
          </section>

          <section className="panel method-card">
            <h2>6 · Playoff y octavos</h2>
            <p>
              Los emparejamientos son deterministas: 9 vs 24, 10 vs 23, …, 16 vs
              17. El mejor clasificado juega la vuelta en casa. Cada eliminatoria
              se resuelve simulando internamente la eliminatoria a doble partido.
            </p>
            <p>
              Si el agregado queda empatado, se juegan 30 minutos de prórroga
              con la ventaja reducida a un tercio. Si sigue el empate, los
              penaltis se resuelven al 50%. No hay regla del gol fuera de casa.
            </p>
            <p>
              La probabilidad de octavos de cada equipo combina acabar entre los
              ocho primeros y ganar el playoff. No se simulan octavos, cuartos,
              semifinales ni final en esta versión.
            </p>
          </section>
        </div>

        <div className="method-grid">
          <section className="panel method-card">
            <h2>7 · Qué no es</h2>
            <ul>
              <li>No incorpora lesiones, sanciones, alineaciones ni mercado.</li>
              <li>El ELO no se actualiza dentro de la simulación.</li>
              <li>La final se trata como neutral.</li>
              <li>La muestra de calibración es corta y las eliminatorias cambian el contexto.</li>
              <li>Una probabilidad alta no es una garantía.</li>
            </ul>
          </section>

          <section className="panel method-card">
            <h2>8 · Reproducibilidad</h2>
            <p>
              El panel usa 10.000 simulaciones con semilla 42. La misma semilla
              produce el mismo resultado. Los scripts permiten regenerar el
              histórico y comprobar el replay.
            </p>
            <pre className="formula">{`cd backend
python scripts/calibrate_champions.py
python scripts/verify_champions.py`}</pre>
            <p>
              El informe de calibración está en{" "}
              <code>docs/champions-calibration.md</code>.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
