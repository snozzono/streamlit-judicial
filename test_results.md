# Test Results — Asistente Tributario RAG

**Fecha:** 2026-04-22 00:25:10  
**Parámetros:** k=8, temperatura=0.1  
**Resultado global:** 7 PASS / 2 FAIL de 9 consultas

---

## [T01] ✅ PASS — DL 825 — IVA

**Consulta:** ¿Qué actividades están exentas de IVA según el artículo 12?  
**Tiempo:** 5.0s  |  **Fragmentos recuperados:** 8

**Validaciones:**
- ✅ Análisis no vacío
- ✅ Al menos un artículo citado
- ✅ Sección Limitaciones presente
- ✅ Fragmentos fuente recuperados

**Análisis:**
De acuerdo con el artículo 12° de la normativa tributaria, están exentas del impuesto establecido en este Título las siguientes actividades:

A.- Las ventas y demás operaciones que recaigan sobre los siguientes bienes:
1º. Los vehículos motorizados usados, con las excepciones que se detallan en el mismo artículo, que incluyen los casos en que se prevé la letra m) del artículo 8º, los vehículos que se importen y aquellos que se transfieran en virtud del ejercicio de la opción de compra contenida en un contrato de arrendamiento con opción de compra. También se excluyen de esta exención los vehículos motorizados usados que no hayan pagado el impuesto al momento de producirse la internación por estar acogidos a alguna franquicia.

Por lo tanto, la exención se aplica principalmente a las ventas de vehículos motorizados usados, salvo en los casos mencionados.

**Artículos citados:**
- Ley 19506
- Art. 12°

**Limitaciones:**
Ninguna

**Fuentes:**
- Fragmento 1: DL-825_31-DIC-1974.pdf, pág. 37
- Fragmento 2: DL-825_31-DIC-1974.pdf, pág. 6
- Fragmento 3: DL-824_31-DIC-1974.pdf, pág. 171
- Fragmento 4: DL-825_31-DIC-1974.pdf, pág. 19
- Fragmento 5: DL-825_31-DIC-1974.pdf, pág. 53
- Fragmento 6: DL-824_31-DIC-1974.pdf, pág. 103
- Fragmento 7: DL-830_31-DIC-1974.pdf, pág. 77
- Fragmento 8: DL-825_31-DIC-1974.pdf, pág. 10

---

## [T02] ❌ FAIL — DL 825 — IVA

**Consulta:** ¿Cuál es la tasa general del IVA y en qué casos se aplica una tasa diferenciada?  
**Tiempo:** 2.0s  |  **Fragmentos recuperados:** 8

**Validaciones:**
- ✅ Análisis no vacío
- ❌ Al menos un artículo citado — La sección ## Artículos citados está vacía.
- ❌ Sección Limitaciones presente — La sección ## Limitaciones está vacía.
- ✅ Fragmentos fuente recuperados

**Análisis:**
La normativa disponible no cubre esta consulta. Consulte directamente con un profesional.

**Fuentes:**
- Fragmento 1: DL-824_31-DIC-1974.pdf, pág. 154
- Fragmento 2: DL-824_31-DIC-1974.pdf, pág. 147
- Fragmento 3: DL-824_31-DIC-1974.pdf, pág. 153
- Fragmento 4: DL-824_31-DIC-1974.pdf, pág. 198
- Fragmento 5: DL-824_31-DIC-1974.pdf, pág. 160
- Fragmento 6: DL-825_31-DIC-1974.pdf, pág. 37
- Fragmento 7: DL-824_31-DIC-1974.pdf, pág. 169
- Fragmento 8: DL-824_31-DIC-1974.pdf, pág. 57

---

## [T03] ✅ PASS — DL 824 — Renta

**Consulta:** ¿Qué se entiende por renta según el DL 824 y qué rentas están exentas?  
**Tiempo:** 4.5s  |  **Fragmentos recuperados:** 8

**Validaciones:**
- ✅ Análisis no vacío
- ✅ Al menos un artículo citado
- ✅ Sección Limitaciones presente
- ✅ Fragmentos fuente recuperados

**Análisis:**
De acuerdo con el Decreto Ley 824, se entiende por "renta" a los ingresos que constituyan utilidades o beneficios que rinda una cosa o actividad, así como todos los beneficios, utilidades e incrementos de patrimonio que se perciban o devenguen, sin importar su naturaleza, origen o denominación (artículo 2°). 

En cuanto a las rentas exentas, el artículo 1° N° 19 d) de la Ley 20630 establece que la obligación de incluir las rentas exentas en la renta bruta global no regirá respecto de aquellas rentas que se encuentren exentas del impuesto global complementario, siempre que estas rentas provengan de contratos suscritos por autoridad competente, conforme a la ley vigente al momento de la concesión de las franquicias respectivas. Además, el artículo 42° del DL 824 menciona que se dará crédito por el impuesto único a la renta retenido por remuneraciones, lo que implica que ciertas rentas pueden estar exentas de impuestos bajo condiciones específicas.

**Artículos citados:**
- Decreto Ley 824, Artículo 2°
- Ley 20630, Art. 1° N° 19 d)

**Limitaciones:**
Ninguna

**Fuentes:**
- Fragmento 1: DL-824_31-DIC-1974.pdf, pág. 157
- Fragmento 2: DL-824_31-DIC-1974.pdf, pág. 57
- Fragmento 3: DL-824_31-DIC-1974.pdf, pág. 0
- Fragmento 4: DL-824_31-DIC-1974.pdf, pág. 85
- Fragmento 5: DL-824_31-DIC-1974.pdf, pág. 0
- Fragmento 6: DL-824_31-DIC-1974.pdf, pág. 158
- Fragmento 7: DL-824_31-DIC-1974.pdf, pág. 185
- Fragmento 8: DL-824_31-DIC-1974.pdf, pág. 104

---

## [T04] ✅ PASS — DL 824 — Renta

**Consulta:** ¿Cómo se determina la base imponible del impuesto de primera categoría?  
**Tiempo:** 4.7s  |  **Fragmentos recuperados:** 8

**Validaciones:**
- ✅ Análisis no vacío
- ✅ Al menos un artículo citado
- ✅ Sección Limitaciones presente
- ✅ Fragmentos fuente recuperados

**Análisis:**
La base imponible del impuesto de primera categoría se determina sobre la renta efectiva, la cual debe ser calculada conforme a un balance general que se elabore según contabilidad completa, de acuerdo con lo establecido en el artículo 14 A de la normativa tributaria. En el caso de empresas que no lleven contabilidad completa, se aplican disposiciones específicas que permiten determinar la base imponible de manera simplificada.

Además, se debe considerar que las rentas que soportaron impuestos en el extranjero, percibidas por personas naturales domiciliadas o residentes en Chile, se encuentran exentas del impuesto de primera categoría, siempre que no formen parte de los activos asignados a su empresa individual. Sin embargo, estas rentas deben incorporarse a la base imponible incrementándose en una cantidad equivalente al crédito por impuesto de primera categoría, conforme a lo dispuesto en los artículos 56 número 3) y 63.

Es importante señalar que la base imponible se afectará con los impuestos finales en el mismo ejercicio en que se determine, y no se podrá deducir ningún crédito o rebaja, salvo los que se establecen en la normativa aplicable.

**Artículos citados:**
- Artículo 14 A
- Artículo 41 G
- Artículo 56 número 3)
- Artículo 63

**Limitaciones:**
Ninguna.

**Fuentes:**
- Fragmento 1: DL-824_31-DIC-1974.pdf, pág. 17
- Fragmento 2: DL-824_31-DIC-1974.pdf, pág. 14
- Fragmento 3: DL-824_31-DIC-1974.pdf, pág. 129
- Fragmento 4: DL-824_31-DIC-1974.pdf, pág. 114
- Fragmento 5: DL-824_31-DIC-1974.pdf, pág. 32
- Fragmento 6: DL-824_31-DIC-1974.pdf, pág. 91
- Fragmento 7: DL-824_31-DIC-1974.pdf, pág. 58
- Fragmento 8: DL-824_31-DIC-1974.pdf, pág. 165

---

## [T05] ✅ PASS — DL 830 — Código Tributario

**Consulta:** ¿Cuáles son los plazos de prescripción de la acción del SII para cobrar impuestos?  
**Tiempo:** 5.1s  |  **Fragmentos recuperados:** 8

**Validaciones:**
- ✅ Análisis no vacío
- ✅ Al menos un artículo citado
- ✅ Sección Limitaciones presente
- ✅ Fragmentos fuente recuperados

**Análisis:**
La acción del Servicio de Impuestos Internos (SII) para perseguir el pago de impuestos, intereses, sanciones y demás recargos prescribe en los plazos establecidos en el artículo 201 de la Ley 19506. Según este artículo, los plazos de prescripción son los siguientes:

1. **Plazo general**: La acción prescribe en tres años contados desde la fecha en que se cometió la infracción.
2. **Interrupción de la prescripción**: Los plazos de prescripción se interrumpen en los siguientes casos:
   - Desde que intervenga un reconocimiento u obligación escrita.
   - Desde que se realice una notificación administrativa de un giro o liquidación.
   - Desde que se inicie un requerimiento judicial.

Además, se establece que si se requiere al contribuyente en los términos del inciso tercero del artículo 63, los plazos se aumentarán en un mes (Ley 21039). También se menciona que el plazo de prescripción puede ser ampliado en ciertas circunstancias, como en el caso de que se trate de impuestos sujetos a declaración que no se hayan presentado o que sean maliciosamente falsos, donde el plazo se extiende a seis años (Ley 19506).

**Artículos citados:**
- Ley 19506, Artículo 201
- Ley 21039

**Limitaciones:**
Ninguna.

**Fuentes:**
- Fragmento 1: DL-830_31-DIC-1974.pdf, pág. 166
- Fragmento 2: DL-830_31-DIC-1974.pdf, pág. 166
- Fragmento 3: DL-830_31-DIC-1974.pdf, pág. 163
- Fragmento 4: DL-830_31-DIC-1974.pdf, pág. 139
- Fragmento 5: DL-830_31-DIC-1974.pdf, pág. 79
- Fragmento 6: DL-830_31-DIC-1974.pdf, pág. 138
- Fragmento 7: DL-830_31-DIC-1974.pdf, pág. 52
- Fragmento 8: DL-830_31-DIC-1974.pdf, pág. 164

---

## [T06] ✅ PASS — DL 830 — Código Tributario

**Consulta:** ¿Qué sanciones contempla el Código Tributario para la declaración maliciosamente falsa?  
**Tiempo:** 4.2s  |  **Fragmentos recuperados:** 8

**Validaciones:**
- ✅ Análisis no vacío
- ✅ Al menos un artículo citado
- ✅ Sección Limitaciones presente
- ✅ Fragmentos fuente recuperados

**Análisis:**
El Código Tributario establece sanciones específicas para las declaraciones maliciosamente falsas en su artículo 97. Según el inciso primero del número 4º de dicho artículo, la emisión o utilización de declaraciones maliciosamente falsas se sancionará con una multa que puede variar entre el cien por ciento y el trescientos por ciento del valor del tributo defraudado, además de la pena de presidio menor en su grado máximo. Esta normativa se aplica a aquellos casos en que se induzca a la liquidación de un impuesto inferior al que realmente corresponde, así como a la omisión maliciosa de asientos contables relacionados con operaciones gravadas.

Además, se menciona que la entrega maliciosa de información incompleta o falsa en la declaración jurada, que resulte en una devolución indebida o superior a la que correspondiera, también será sancionada conforme a lo dispuesto en el mismo artículo 97 del Código Tributario.

**Artículos citados:**
- Art. 97 del Código Tributario

**Limitaciones:**
Ninguna

**Fuentes:**
- Fragmento 1: DL-830_31-DIC-1974.pdf, pág. 108
- Fragmento 2: DL-824_31-DIC-1974.pdf, pág. 192
- Fragmento 3: DL-830_31-DIC-1974.pdf, pág. 102
- Fragmento 4: DL-824_31-DIC-1974.pdf, pág. 213
- Fragmento 5: DL-830_31-DIC-1974.pdf, pág. 102
- Fragmento 6: DL-830_31-DIC-1974.pdf, pág. 110
- Fragmento 7: DL-830_31-DIC-1974.pdf, pág. 105
- Fragmento 8: DL-824_31-DIC-1974.pdf, pág. 124

---

## [T07] ✅ PASS — Caso borde — fuente externa

**Consulta:** ¿Qué obligaciones tributarias tiene una empresa extranjera sin domicilio en Chile que presta servicios digitales?  
**Tiempo:** 5.3s  |  **Fragmentos recuperados:** 8

**Validaciones:**
- ✅ Análisis no vacío
- ✅ Al menos un artículo citado
- ✅ Sección Limitaciones presente
- ✅ Fragmentos fuente recuperados

**Análisis:**
Una empresa extranjera sin domicilio en Chile que presta servicios digitales tiene varias obligaciones tributarias según la normativa chilena. En primer lugar, el artículo 5° de la Ley 21210 establece que el impuesto gravará los servicios prestados o utilizados en el territorio nacional, independientemente de dónde se pague o perciba la remuneración. Esto implica que si la empresa presta servicios digitales que se consideran utilizados en Chile, estará sujeta al impuesto correspondiente.

Además, el artículo 60° de la misma ley indica que las personas naturales y jurídicas que no tengan residencia ni domicilio en Chile, y que perciban rentas de fuente chilena, deberán pagar un impuesto adicional del 35% sobre dichas rentas, salvo que se encuentren exentas conforme a lo dispuesto en el artículo 59° bis, que establece ciertas exenciones para contribuyentes no domiciliados que presten servicios a personas naturales que no son contribuyentes del impuesto.

Por lo tanto, la empresa extranjera deberá:
1. Determinar si los servicios digitales que presta son considerados utilizados en Chile, lo cual se presume si se cumplen ciertas condiciones, como la geolocalización del usuario (artículo 5°).
2. Pagar el impuesto adicional del 35% sobre las rentas obtenidas de la prestación de estos servicios, a menos que califique para alguna exención.

**Artículos citados:**
- Ley 21210, Art. 5°
- Ley 21210, Art. 60°
- Ley 21210, Art. 59° bis

**Limitaciones:**
No se abordan aspectos específicos sobre la forma de declaración y pago del impuesto, ni sobre posibles deducciones o créditos que la empresa podría tener derecho a solicitar.

**Fuentes:**
- Fragmento 1: DL-825_31-DIC-1974.pdf, pág. 7
- Fragmento 2: DL-825_31-DIC-1974.pdf, pág. 4
- Fragmento 3: DL-824_31-DIC-1974.pdf, pág. 176
- Fragmento 4: DL-824_31-DIC-1974.pdf, pág. 112
- Fragmento 5: DL-830_31-DIC-1974.pdf, pág. 26
- Fragmento 6: DL-824_31-DIC-1974.pdf, pág. 117
- Fragmento 7: DL-824_31-DIC-1974.pdf, pág. 138
- Fragmento 8: DL-824_31-DIC-1974.pdf, pág. 171

---

## [T08] ✅ PASS — Caso borde — incumplimiento

**Consulta:** ¿Qué pasa si un contribuyente no presenta su declaración de impuestos dentro del plazo?  
**Tiempo:** 5.4s  |  **Fragmentos recuperados:** 8

**Validaciones:**
- ✅ Análisis no vacío
- ✅ Al menos un artículo citado
- ✅ Sección Limitaciones presente
- ✅ Fragmentos fuente recuperados

**Análisis:**
Si un contribuyente no presenta su declaración de impuestos dentro del plazo establecido, se enfrenta a diversas sanciones y consecuencias. Según el artículo 2 N° 3 i) de la Ley 21713, el retardo u omisión en la presentación de declaraciones o informes que constituyan la base inmediata para la determinación o liquidación de un impuesto puede resultar en una multa que oscila entre 10 a 50 unidades tributarias anuales. Esta multa no podrá exceder del límite mayor entre el equivalente al 15% del capital propio del contribuyente o el 5% de su capital efectivo.

Además, el artículo 36 bis de la Ley 20431 establece que los contribuyentes que incurran en errores en su declaración pueden presentar una nueva declaración antes de que exista liquidación o giro del Servicio, corrigiendo las anomalías, aunque se encuentren vencidos los plazos legales. Sin embargo, esto no exime al contribuyente de las sanciones y recargos que correspondan por las cantidades no ingresadas oportunamente.

Por lo tanto, la falta de presentación de la declaración dentro del plazo legal no solo conlleva multas, sino que también puede afectar la situación tributaria del contribuyente, obligándolo a regularizar su situación mediante la presentación de declaraciones rectificatorias, si es que se encuentra dentro de los plazos establecidos para ello.

**Artículos citados:**
- Ley 21713, Art. 2 N° 3 i)
- Ley 20431, Art. 36 bis

**Limitaciones:**
No se abordan las circunstancias específicas que podrían mitigar las sanciones o las opciones de apelación que el contribuyente podría tener.

**Fuentes:**
- Fragmento 1: DL-830_31-DIC-1974.pdf, pág. 36
- Fragmento 2: DL-830_31-DIC-1974.pdf, pág. 44
- Fragmento 3: DL-824_31-DIC-1974.pdf, pág. 124
- Fragmento 4: DL-830_31-DIC-1974.pdf, pág. 161
- Fragmento 5: DL-830_31-DIC-1974.pdf, pág. 101
- Fragmento 6: DL-830_31-DIC-1974.pdf, pág. 83
- Fragmento 7: DL-824_31-DIC-1974.pdf, pág. 78
- Fragmento 8: DL-830_31-DIC-1974.pdf, pág. 166

---

## [T09] ❌ FAIL — Fuera de corpus

**Consulta:** ¿Cuáles son los requisitos para obtener una visa de trabajo en Chile?  
**Tiempo:** 1.6s  |  **Fragmentos recuperados:** 8

**Validaciones:**
- ✅ Análisis no vacío
- ✅ Sin artículos inventados (fuera de corpus)
- ❌ Sección Limitaciones presente — La sección ## Limitaciones está vacía.
- ✅ Fragmentos fuente recuperados

**Análisis:**
La normativa disponible no cubre esta consulta. Consulte directamente con un profesional.

**Fuentes:**
- Fragmento 1: DL-825_31-DIC-1974.pdf, pág. 4
- Fragmento 2: DL-825_31-DIC-1974.pdf, pág. 12
- Fragmento 3: DL-825_31-DIC-1974.pdf, pág. 14
- Fragmento 4: DL-824_31-DIC-1974.pdf, pág. 176
- Fragmento 5: DL-825_31-DIC-1974.pdf, pág. 44
- Fragmento 6: DL-825_31-DIC-1974.pdf, pág. 15
- Fragmento 7: DL-825_31-DIC-1974.pdf, pág. 14
- Fragmento 8: DL-824_31-DIC-1974.pdf, pág. 98

---
