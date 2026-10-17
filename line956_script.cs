
#region Usings
using System;
using System.Collections.Generic;
using System.Linq;
using Rhino;
using Rhino.Geometry;
using Rhino.Geometry.Intersect;
#endregion

public class Script_Instance : GH_ScriptInstance
{
  private void RunScript(
    Point3d Pt_Pupil,
    Point3d Pt_Right,
    Point3d Pt_Up,
    Brep LensBrep,
    double Distance_D,
    double Offset_Hd,
    double Width,
    double Height,
    double Keystone_V,
    double Keystone_H,
    double FocalLength,
    double VialDistance,
    int NumSampleRays,
    ref object IncidentCone,
    ref object CollimatedBeam,
    ref object SpilloverCone,
    ref object LensFootprint,
    ref object RayLines,
    ref object Info)
  {
    List<string> log = new List<string>();

    if (!Pt_Pupil.IsValid || !Pt_Right.IsValid || !Pt_Up.IsValid)
    {
      log.Add("ERROR: Pt_Pupil, Pt_Right, or Pt_Up is invalid.");
      Info = log;
      return;
    }

    if (LensBrep == null || !LensBrep.IsValid)
    {
      log.Add("ERROR: LensBrep is missing or invalid.");
      Info = log;
      return;
    }

    // ---------------------------------------------------------------------
    // 1. Unambiguous 3-Point Orthogonal Coordinate System
    // ---------------------------------------------------------------------
    Point3d origin = Pt_Pupil;

    // Local Width Axis (X) along the projector's native width
    Vector3d right = Pt_Right - origin;
    right.Unitize();

    // Local Height Axis (Y) along the projector's native height (offset direction)
    Vector3d up = Pt_Up - origin;
    up.Unitize();

    // Optical Throw Axis (Z) is strictly normal to the front panel: X x Y
    Vector3d fwd = Vector3d.CrossProduct(right, up);
    fwd.Unitize();

    // Re-orthogonalize UP to guarantee a 100.0% perfect Cartesian coordinate frame
    up = Vector3d.CrossProduct(fwd, right);
    up.Unitize();

    // ---------------------------------------------------------------------
    // 2. Optical Parameters & Tolerances
    // ---------------------------------------------------------------------
    double dThrow = (Distance_D > 0) ? Distance_D : 4050.0;
    double hOffset = (Offset_Hd != 0) ? Offset_Hd : 93.0;
    double w = (Width > 0) ? Width : 3320.0;
    double h = (Height > 0) ? Height : 1870.0;
    double f = (FocalLength > 0) ? FocalLength : 200.0;
    double vDist = (VialDistance > 0) ? VialDistance : 50.0;
    int nRays = (NumSampleRays > 3) ? NumSampleRays : 36;

    double tol = (RhinoDoc.ActiveDoc != null && RhinoDoc.ActiveDoc.ModelAbsoluteTolerance > 0)
      ? RhinoDoc.ActiveDoc.ModelAbsoluteTolerance : 0.01;
    tol = Math.Max(tol, 0.001);

    // ---------------------------------------------------------------------
    // 3. Build Full 16:9 Frustum with Keystone Warping
    // ---------------------------------------------------------------------
    // Screen center translated by throw distance and vertical lens shift
    Point3d targetCenter = origin + (fwd * dThrow) + (up * hOffset);
    Plane screenPlane = new Plane(targetCenter, right, up);

    // Apply Keystone Rotations (Degrees)
    if (Math.Abs(Keystone_V) > 0.001)
    {
      double radV = Keystone_V * (Math.PI / 180.0);
      screenPlane.Rotate(radV, screenPlane.XAxis, targetCenter);
    }
    if (Math.Abs(Keystone_H) > 0.001)
    {
      double radH = Keystone_H * (Math.PI / 180.0);
      screenPlane.Rotate(radH, screenPlane.YAxis, targetCenter);
    }

    Interval xDom = new Interval(-w * 0.5, w * 0.5);
    Interval yDom = new Interval(-h * 0.5, h * 0.5);
    Rectangle3d rect = new Rectangle3d(screenPlane, xDom, yDom);

    Point3d c0 = rect.Corner(0);
    Point3d c1 = rect.Corner(1);
    Point3d c2 = rect.Corner(2);
    Point3d c3 = rect.Corner(3);

    // 5-Surface Solid Frustum
    List<Brep> pyramidFaces = new List<Brep>
    {
      Brep.CreateFromCornerPoints(origin, c0, c1, tol),
      Brep.CreateFromCornerPoints(origin, c1, c2, tol),
      Brep.CreateFromCornerPoints(origin, c2, c3, tol),
      Brep.CreateFromCornerPoints(origin, c3, c0, tol),
      Brep.CreateFromCornerPoints(c0, c1, c2, c3, tol)
    };

    Brep[] joined = Brep.JoinBreps(pyramidFaces.Where(p => p != null), tol);
    if (joined == null || joined.Length == 0)
    {
      log.Add("ERROR: Could not join frustum Brep.");
      Info = log;
      return;
    }
    Brep activeCone = joined[0];

    // ---------------------------------------------------------------------
    // 4. Locate Front Optical Face of Collimating Lens
    // ---------------------------------------------------------------------
    BrepFace frontFace = null;
    double minFaceDist = double.MaxValue;
    foreach (BrepFace face in LensBrep.Faces)
    {
      double um = (face.Domain(0).Min + face.Domain(0).Max) * 0.5;
      double vm = (face.Domain(1).Min + face.Domain(1).Max) * 0.5;
      Point3d ptF = face.PointAt(um, vm);
      double dist = ptF.DistanceTo(origin);
      if (dist < minFaceDist)
      {
        minFaceDist = dist;
        frontFace = face;
      }
    }

    if (frontFace == null)
    {
      IncidentCone = activeCone;
      Info = log;
      return;
    }

    AreaMassProperties amp = AreaMassProperties.Compute(frontFace);
    double uc = (frontFace.Domain(0).Min + frontFace.Domain(0).Max) * 0.5;
    double vc = (frontFace.Domain(1).Min + frontFace.Domain(1).Max) * 0.5;
    Point3d lensCenter = (amp != null) ? amp.Centroid : frontFace.PointAt(uc, vc);
    Vector3d lensNormal = frontFace.NormalAt(uc, vc);
    if ((lensNormal * (lensCenter - origin)) < 0) lensNormal.Reverse();
    lensNormal.Unitize();

    // ---------------------------------------------------------------------
    // 5. Extract Glass Footprint (Handles Partial Lens Coverage)
    // ---------------------------------------------------------------------
    Curve footprint = null;
    Brep faceBrep = frontFace.DuplicateFace(false);

    Curve[] intCrvs;
    Point3d[] intPts;
    if (Intersection.BrepBrep(activeCone, faceBrep, tol, out intCrvs, out intPts) && intCrvs != null && intCrvs.Length > 0)
    {
      Curve[] joinedCrvs = Curve.JoinCurves(intCrvs, tol);
      if (joinedCrvs != null && joinedCrvs.Length > 0 && joinedCrvs[0].IsClosed)
        footprint = joinedCrvs[0];
    }

    // Boolean Clipping if cone spills outside circular lens
    if (footprint == null)
    {
      Brep[] clipped = Brep.CreateBooleanIntersection(activeCone, LensBrep, tol);
      if (clipped != null && clipped.Length > 0)
      {
        foreach (BrepFace cf in clipped[0].Faces)
        {
          Point3d cPt = cf.PointAt(0.5, 0.5);
          if (Math.Abs((cPt - lensCenter) * lensNormal) < tol * 5.0)
          {
            Curve[] loops = cf.DuplicateFace(false).DuplicateEdgeCurves(true);
            Curve[] joinedLoops = Curve.JoinCurves(loops, tol);
            if (joinedLoops != null && joinedLoops.Length > 0)
            {
              footprint = joinedLoops[0];
              log.Add("PARTIAL COVERAGE: Footprint clipped by circular lens boundary.");
              break;
            }
          }
        }
      }
    }

    if (footprint == null)
    {
      log.Add("FAILED: Projection cone completely misses lens.");
      IncidentCone = activeCone;
      Info = log;
      return;
    }

    if (!footprint.IsClosed) footprint.MakeClosed(tol);
    LensFootprint = footprint;

    // ---------------------------------------------------------------------
    // 6. Truncated Incident Cone (Pupil -> Lens Glass)
    // ---------------------------------------------------------------------
    Brep[] incLofts = Brep.CreateFromLoft(
      new Curve[] { footprint }, origin, Point3d.Unset, LoftType.Normal, false
    );
    if (incLofts != null && incLofts.Length > 0)
      IncidentCone = incLofts[0].CapPlanarHoles(tol);

    // ---------------------------------------------------------------------
    // 7. Calculate Spillover Cone (Uncollimated Bypass Light)
    // ---------------------------------------------------------------------
    if (IncidentCone is Brep incB)
    {
      Brep[] diff = Brep.CreateBooleanDifference(activeCone, incB, tol);
      if (diff != null && diff.Length > 0)
      {
        SpilloverCone = diff[0];
        log.Add("SPILLOVER: Calculated uncollimated light spilling past lens.");
      }
    }

    // ---------------------------------------------------------------------
    // 8. Collimated Telecentric Beam (Only Light Exiting the Glass)
    // ---------------------------------------------------------------------
    double[] tParams = footprint.DivideByCount(nRays, true);
    if (tParams == null || tParams.Length == 0) { Info = log; return; }

    List<Point3d> ptsVial = new List<Point3d>(tParams.Length);
    List<Line> lines = new List<Line>(tParams.Length * 2);
    List<double> angles = new List<double>(tParams.Length);

    for (int i = 0; i < tParams.Length; i++)
    {
      Point3d pLens = footprint.PointAt(tParams[i]);
      Vector3d vIn = pLens - origin;
      double dAxis = vIn * lensNormal;
      Vector3d vInTrans = vIn - lensNormal * dAxis;

      Vector3d dr = pLens - lensCenter;
      Vector3d drTrans = dr - lensNormal * (dr * lensNormal);

      double dSafe = Math.Max(dAxis, 1e-6);
      double fSafe = Math.Max(f, 1e-6);

      // Paraxial thin lens deflection: vOut = (vIn / d) - (dr / f)
      Vector3d vOutTrans = (vInTrans * (1.0 / dSafe)) - (drTrans * (1.0 / fSafe));
      Vector3d vOut = lensNormal + vOutTrans;
      vOut.Unitize();

      Point3d pVial = pLens + (vOut * vDist);
      ptsVial.Add(pVial);

      lines.Add(new Line(origin, pLens));
      lines.Add(new Line(pLens, pVial));

      double dot = Math.Max(-1.0, Math.Min(1.0, vOut * lensNormal));
      angles.Add(Math.Acos(dot) * (180.0 / Math.PI));
    }

    Curve vialCrv = Curve.CreateInterpolatedCurve(ptsVial, 3);
    if (vialCrv != null)
    {
      if (!vialCrv.IsClosed) vialCrv.MakeClosed(tol);
      Brep[] lofts = Brep.CreateFromLoft(
        new Curve[] { footprint, vialCrv }, Point3d.Unset, Point3d.Unset, LoftType.Normal, false
      );
      if (lofts != null && lofts.Length > 0)
        CollimatedBeam = lofts[0].CapPlanarHoles(tol);
    }

    RayLines = lines;
    double avgA = (angles.Count > 0) ? angles.Average() : 0.0;
    log.Add(string.Format("Distance Projector to Lens: {0:F2} mm", lensCenter.DistanceTo(origin)));
    log.Add(string.Format("Avg Exit Angle: {0:F3} deg", avgA));
    log.Add((avgA < 1.0) ? "Status: COLLIMATED (Telecentric)" : "Status: DIVERGING / CONVERGING");
    Info = log;
  }
}
