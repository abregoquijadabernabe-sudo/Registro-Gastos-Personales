
import os
import sqlite3
import csv
import io
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, flash, make_response

app = Flask(__name__)
app.secret_key = "clave-local-para-desarrollo"

BASE_DATOS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "finanzas.db"
)


def conectar():
    conexion = sqlite3.connect(BASE_DATOS)

    conexion.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT NOT NULL,
            categoria TEXT NOT NULL,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK (tipo IN ('Ingreso', 'Gasto')),
            importe REAL NOT NULL CHECK (importe > 0)
        )
    """)

    conexion.commit()
    return conexion


@app.route("/", methods=["GET", "POST"])
def inicio():
    if request.method == "POST":
        descripcion = request.form.get("descripcion", "").strip()
        categoria = request.form.get("categoria", "").strip()
        fecha = request.form.get("fecha", "").strip()
        tipo = request.form.get("tipo", "").strip()
        importe_texto = request.form.get("importe", "").strip()

        categorias_validas = {
            "Salario",
            "Ventas",
            "Otros ingresos",
            "Alimentación",
            "Transporte",
            "Vivienda",
            "Servicios",
            "Salud",
            "Educación",
            "Entretenimiento",
            "Otros gastos"
        }

        if not descripcion or len(descripcion) > 120:
            flash("Escribe una descripción de hasta 120 caracteres.", "error")
            return redirect(url_for("inicio") + "#registro")

        if categoria not in categorias_validas:
            flash("Selecciona una categoría válida.", "error")
            return redirect(url_for("inicio") + "#registro")

        if tipo not in ("Ingreso", "Gasto"):
            flash("Selecciona si el movimiento es un ingreso o un gasto.", "error")
            return redirect(url_for("inicio") + "#registro")

        try:
            fecha_validada = date.fromisoformat(fecha)
            importe = float(importe_texto)

            if fecha_validada.isoformat() != fecha:
                raise ValueError

            if importe <= 0 or not importe < float("inf"):
                raise ValueError

        except (ValueError, OverflowError):
            flash("Introduce una fecha válida y un importe mayor que cero.", "error")
            return redirect(url_for("inicio") + "#registro")

        conexion = conectar()

        try:
            conexion.execute("""
                INSERT INTO movimientos
                    (descripcion, categoria, fecha, tipo, importe)
                VALUES (?, ?, ?, ?, ?)
            """, (descripcion, categoria, fecha, tipo, importe))

            conexion.commit()
            flash("Movimiento registrado correctamente.", "success")

        except sqlite3.Error:
            conexion.rollback()
            flash("No se pudo guardar el movimiento. Inténtalo de nuevo.", "error")

        finally:
            conexion.close()

        return redirect(url_for("inicio"))

    conexion = conectar()

    try:
        movimientos = conexion.execute("""
            SELECT id, descripcion, categoria, fecha, tipo, importe
            FROM movimientos
            ORDER BY fecha DESC, id DESC
        """).fetchall()

        totales = conexion.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo = 'Ingreso'
                    THEN importe ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN tipo = 'Gasto'
                    THEN importe ELSE 0 END), 0),
                COUNT(*)
            FROM movimientos
        """).fetchone()

    finally:
        conexion.close()

    ingresos = totales[0]
    gastos = totales[1]
    cantidad = totales[2]
    saldo = ingresos - gastos

    return render_template(
        "index.html",
        movimientos=movimientos,
        ingresos=ingresos,
        gastos=gastos,
        saldo=saldo,
        cantidad=cantidad,
        fecha_hoy=date.today().isoformat()
    )


@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    categorias_validas = {
        "Salario", "Ventas", "Otros ingresos",
        "Alimentación", "Transporte", "Vivienda",
        "Servicios", "Salud", "Educación",
        "Entretenimiento", "Otros gastos"
    }

    conexion = conectar()

    movimiento = conexion.execute("""
        SELECT id, descripcion, categoria, fecha, tipo, importe
        FROM movimientos
        WHERE id = ?
    """, (id,)).fetchone()

    conexion.close()

    if movimiento is None:
        flash("El movimiento solicitado no existe.", "error")
        return redirect(url_for("inicio"))

    if request.method == "POST":
        descripcion = request.form.get("descripcion", "").strip()
        categoria = request.form.get("categoria", "").strip()
        fecha = request.form.get("fecha", "").strip()
        tipo = request.form.get("tipo", "").strip()
        importe_texto = request.form.get("importe", "").strip()

        if not descripcion or len(descripcion) > 120:
            flash("Escribe una descripción de hasta 120 caracteres.", "error")
            return redirect(url_for("editar", id=id))

        if categoria not in categorias_validas:
            flash("Selecciona una categoría válida.", "error")
            return redirect(url_for("editar", id=id))

        if tipo not in ("Ingreso", "Gasto"):
            flash("Selecciona un tipo de movimiento válido.", "error")
            return redirect(url_for("editar", id=id))

        try:
            fecha_validada = date.fromisoformat(fecha)
            importe = float(importe_texto)

            if fecha_validada.isoformat() != fecha:
                raise ValueError

            if not 0 < importe < float("inf"):
                raise ValueError

        except (ValueError, OverflowError):
            flash("Introduce una fecha válida y un importe mayor que cero.", "error")
            return redirect(url_for("editar", id=id))

        conexion = conectar()

        try:
            conexion.execute("""
                UPDATE movimientos
                SET descripcion = ?, categoria = ?, fecha = ?,
                    tipo = ?, importe = ?
                WHERE id = ?
            """, (descripcion, categoria, fecha, tipo, importe, id))

            conexion.commit()
            flash("Movimiento actualizado correctamente.", "success")

        except sqlite3.Error:
            conexion.rollback()
            flash("No se pudo actualizar el movimiento.", "error")

        finally:
            conexion.close()

        return redirect(url_for("inicio"))

    return render_template(
        "editar_movimiento.html",
        movimiento=movimiento
    )


@app.route("/eliminar/<int:id>", methods=["POST"])
def eliminar(id):
    conexion = conectar()

    try:
        resultado = conexion.execute(
            "DELETE FROM movimientos WHERE id = ?",
            (id,)
        )

        if resultado.rowcount == 0:
            flash("El movimiento ya no existe.", "error")
        else:
            conexion.commit()
            flash("Movimiento eliminado correctamente.", "success")

    except sqlite3.Error:
        conexion.rollback()
        flash("No se pudo eliminar el movimiento.", "error")

    finally:
        conexion.close()

    return redirect(url_for("inicio"))

@app.route("/reportes")
def reportes():
    mes = request.args.get("mes", date.today().strftime("%Y-%m"))

    try:
        fecha_mes = date.fromisoformat(mes + "-01")
        if fecha_mes.strftime("%Y-%m") != mes:
            raise ValueError
    except ValueError:
        mes = date.today().strftime("%Y-%m")

    conexion = conectar()

    try:
        totales = conexion.execute("""
            SELECT
                COALESCE(SUM(
                    CASE WHEN tipo = 'Ingreso' THEN importe ELSE 0 END
                ), 0),
                COALESCE(SUM(
                    CASE WHEN tipo = 'Gasto' THEN importe ELSE 0 END
                ), 0),
                COUNT(*)
            FROM movimientos
            WHERE strftime('%Y-%m', fecha) = ?
        """, (mes,)).fetchone()

        categorias = conexion.execute("""
            SELECT categoria, SUM(importe), COUNT(*)
            FROM movimientos
            WHERE strftime('%Y-%m', fecha) = ?
              AND tipo = 'Gasto'
            GROUP BY categoria
            ORDER BY SUM(importe) DESC
        """, (mes,)).fetchall()

        movimientos_mes = conexion.execute("""
            SELECT descripcion, categoria, fecha, tipo, importe
            FROM movimientos
            WHERE strftime('%Y-%m', fecha) = ?
            ORDER BY fecha DESC, id DESC
        """, (mes,)).fetchall()

    finally:
        conexion.close()

    ingresos_mes = totales[0]
    gastos_mes = totales[1]

    return render_template(
        "reportes.html",
        mes=mes,
        ingresos=ingresos_mes,
        gastos=gastos_mes,
        saldo=ingresos_mes - gastos_mes,
        cantidad=totales[2],
        categorias=categorias,
        movimientos=movimientos_mes,
        escala=max(ingresos_mes, gastos_mes, 1),
    )

@app.route("/reportes/exportar")
def exportar_reporte():
    mes = request.args.get(
        "mes",
        date.today().strftime("%Y-%m")
    )

    try:
        fecha_mes = date.fromisoformat(mes + "-01")
        if fecha_mes.strftime("%Y-%m") != mes:
            raise ValueError
    except ValueError:
        flash("Selecciona un mes válido para exportar.", "error")
        return redirect(url_for("reportes"))

    conexion = conectar()

    try:
        movimientos = conexion.execute("""
            SELECT descripcion, categoria, fecha, tipo, importe
            FROM movimientos
            WHERE strftime('%Y-%m', fecha) = ?
            ORDER BY fecha DESC, id DESC
        """, (mes,)).fetchall()
    finally:
        conexion.close()

    archivo = io.StringIO()
    escritor = csv.writer(archivo, delimiter=";")

    escritor.writerow([
        "Descripción",
        "Categoría",
        "Fecha",
        "Tipo",
        "Importe"
    ])

    for movimiento in movimientos:
        escritor.writerow(movimiento)

    respuesta = make_response(
        "\ufeff" + archivo.getvalue()
    )
    respuesta.headers["Content-Type"] = (
        "text/csv; charset=utf-8"
    )
    respuesta.headers["Content-Disposition"] = (
        f'attachment; filename="reporte_finanzas_{mes}.csv"'
    )

    return respuesta

if __name__ == "__main__":
    conectar().close()
    app.run(debug=True)
