/**
 * La couche d'état d'une surface interactive.
 *
 * `md-ripple` et `md-focus-ring` s'attachent à l'élément parent : il suffit de
 * poser ce composant à l'intérieur d'un bouton `position: relative`, et la
 * surface hérite du survol, de la pression et de l'anneau de focus M3.
 *
 * `inward` fait rentrer l'anneau à l'intérieur du conteneur. Il le faut dès que
 * le parent est rogné (`overflow: hidden`) : sinon l'anneau, dessiné 2 dp en
 * dehors, est coupé.
 */
export function StateLayer({ inward = false }: { inward?: boolean }) {
  return (
    <>
      <md-ripple />
      {inward ? <md-focus-ring inward /> : <md-focus-ring />}
    </>
  );
}
